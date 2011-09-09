#!/usr/bin/env python

###############################################################################
# EDIT HERE.

class Admin:
	EmailAddress = 'root@localhost' # Used for notices.
	MailserverHostName = 'localhost'
	MailserverPort = 25
	Notify = 1 # Would you like E-mail notifcations? 0: No, 1: Yes

class MailWasher:
	# A username or password are not required. They are extracted from the database.
	HostName = 'localhost'
	Port = '4044'
	Username = 'admin'
	Password = 'password'

class Plesk:
	HostName = 'localhost'
	Port = '8443'
	Username = 'admin'
	Password = 'password'

# END EDIT. It would pay to leave everything below alone.
###############################################################################

import os, sys, tempfile, pycurl, StringIO, smtplib, xml.dom.minidom, json, urllib
from subprocess import Popen, PIPE
from email.mime.text import MIMEText

# Handles all E-mail notification.
class Notifier:
	MailTag = '[Plesk-MWES]'
	
	@staticmethod
	def Send(message):
		if not Admin.Notify: return # Do we actually want to send E-mail?
		message['From'] = Admin.EmailAddress
		message['To'] = Admin.EmailAddress
		smtp_server = smtplib.SMTP(Admin.MailserverHostName, Admin.MailserverPort)
		smtp_server.sendmail(Admin.EmailAddress, Admin.EmailAddress, message.as_string())
		smtp_server.quit()
		
	@staticmethod
	def AddSuccess(domain_name):
		message = MIMEText('Added "%s" to MWES.' % (domain_name))
		message['Subject'] = '%s Added "%s" to MWES.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def AddFailure(domain_name):
		message = MIMEText('Failed to add "%s" to MWES. Please resolve this issue manually.' % (domain_name))
		message['Subject'] = '%s Failed to add "%s" to MWES.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def RenameSuccess(domain_name_old, domain_name_new):
		message = MIMEText('Renamed "%s" to "%s" in MWES.' % (domain_name_old, domain_name_new))
		message['Subject'] = '%s Renamed "%s" to "%s" in MWES.' % (Notifier.MailTag, domain_name_old, domain_name_new)
		Notifier.Send(message)
		
	@staticmethod
	def RenameFailure(domain_name_old, domain_name_new):
		message = MIMEText('Failed to rename "%s" to "%s" in MWES. Please resolve this issue manually.' % (domain_name_old, domain_name_new))
		message['Subject'] = '%s Failed to rename "%s" to "%s" in MWES.' % (Notifier.MailTag, domain_name_old, domain_name_new)
		Notifier.Send(message)
		
	@staticmethod
	def RemoveSuccess(domain_name):
		message = MIMEText('Removed "%s" from MWES.' % (domain_name))
		message['Subject'] = '%s Removed "%s" from MWES.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def RemoveFailure(domain_name):
		message = MIMEText('Failed to remove "%s" from MWES. Please resolve this issue manually.' % (domain_name))
		message['Subject'] = '%s Failed to remove "%s" from MWES.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def SynchronizationReport(new_domains, old_domains, failed_domains):
		report = ''
		if new_domains:
			report += "Adding:\n"
			for domain_name in new_domains:
				status = 'OK'
				if domain_name in failed_domains: status = 'FAIL'
				report += "\t%s [%s]\n" % (domain_name, status)
		if old_domains:
			report += "Removing:\n"
			for domain_name in old_domains:
				status = 'OK'
				if domain_name in failed_domains: status = 'FAIL'
				report += "\t%s [%s]\n" % (domain_name, status)
		
		message = MIMEText(report)
		message['Subject'] = '%s Synchronization Report' % (Notifier.MailTag)
		Notifier.Send(message)

# This makes Plesk API calls a LOT easier to diagnose when they go wrong.
class PleskRPCError(Exception):

	def __init__(self, error_code, error_text):
		self.error_code = error_code
		self.error_text = error_text
		
	def __str__(self):
		return '[%s] %s' % (self.error_code, self.error_text)


# This class handles all communication with Plesk via Plesk's XML based API.
class PleskRPCAgent:

	buffer = None # Buffer for incoming data.
	curl = None # Curl agent.

	def __init__(self, hostname, port, username, password):
		self.curl = pycurl.Curl()
		
		agent_url = 'https://' + hostname + ':' + port + '/enterprise/control/agent.php'
		header = ['HTTP_AUTH_LOGIN: ' + username, 'HTTP_AUTH_PASSWD: ' + password, 'Content-Type: text/xml']
		
		self.curl.setopt(pycurl.URL, agent_url)
		self.curl.setopt(pycurl.SSL_VERIFYHOST, 0)
		self.curl.setopt(pycurl.SSL_VERIFYPEER, 0)
		self.curl.setopt(pycurl.HTTPHEADER, header)
		
		self.reset_buffer()

	# Check the response to ensure it was processed correctly. Let the user know what went wrong if anything did.
	def check_response_status(self): 
		# Parse buffer as XML.
		dom = xml.dom.minidom.parseString(self.buffer.getvalue())
		# If the system element exists we have a problem, but we'll check for an error specifically anyway.
		system_response = dom.getElementsByTagName('system')
		if len(system_response) > 0:
			error_code = system_response[0].getElementsByTagName('errcode')[0].childNodes[0].data
			error_text = system_response[0].getElementsByTagName('errtext')[0].childNodes[0].data
			raise PleskRPCError(error_code, error_text)
	
	# Reset Curl's buffer.
	def reset_buffer(self):
		# Destroy buffer if it exists, and release memory.
		if self.buffer: self.buffer.close()
		
		# New buffer.
		self.buffer = StringIO.StringIO()
		
		# Let Curl know where it is to write received data (buffer).
		self.curl.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
	
	# Handle sending the packet and verifying the response. Return XML dom of Plesk's return.
	def process(self, packet):
		self.reset_buffer()
	
		# Set the packet.
		self.curl.setopt(pycurl.POSTFIELDS, packet)
		
		# Send packet.
		self.curl.perform()
		
		# Now we need to check if the Plesk RPC returned a useful result.
		try:
			self.check_response_status()
		except PleskRPCError, e:
			raise e

		# Return received data.
		return xml.dom.minidom.parseString(self.buffer.getvalue())
	
	# Return all domains stored in Plesk.
	def domains(self):
		packet = '<packet version="1.5.2.0"><domain><get><filter /><dataset><gen_info /></dataset></get></domain></packet>'

		# Send packet and get XML DOM response.
		dom = self.process(packet)
		
		domains = []
		for domain in dom.getElementsByTagName('name'):
			domains.append(str(domain.childNodes[0].data)) # Convert from Unicode to str.
		
		return sorted(domains)
	
	# Return all subdomains stored in Plesk.
	def subdomains(self):
		packet = '<packet version="1.5.2.0"><subdomain><get><filter /></get></subdomain></packet>'

		# Send packet and get XML DOM response.
		dom = self.process(packet)
		
		subdomains = []
		for subdomain in dom.getElementsByTagName('data'):
			for node in subdomain.childNodes:
				if node.nodeName == 'name':
					subdomains.append(str(node.childNodes[0].data)) # Convert from Unicode to str.
		
		return sorted(subdomains)
	
	# Return all domain aliases stored in Plesk.
	def domain_aliases(self):
		packet = '<packet version="1.5.2.0"><domain_alias><get><filter /></get></domain_alias></packet>'

		# Send packet and get XML DOM response.
		dom = self.process(packet)
		
		subdomains = []
		for subdomain in dom.getElementsByTagName('info'):
			for node in subdomain.childNodes:
				if node.nodeName == 'name':
					subdomains.append(str(node.childNodes[0].data)) # Convert from Unicode to str.
		
		return sorted(subdomains)
	
	# Return a list containing all domains, subdomains and domain aliases stored in Plesk.
	def get_all_domains(self):
		return sorted(agent.domains() + agent.subdomains() + agent.domain_aliases())

		
# This control handles MWES operations via a servlet Firetrust kindly organized for me (thanks guys!)
class MWESControl:
	
	# Web-based hook.
	buffer = None
	curl = None
	
	agent_url = '' # URL of MailWasher.
	
	def __init__(self, hostname, port, username, password):
		
		# Store.
		self.agent_url = 'http://%s:%s' % (hostname, port)
		
		# We need a cookie for MailWasher.
		self.cookie_fd, self.cookie_path = tempfile.mkstemp('-mwc')
		
		# Connect to web interface.
		self.connect(username, password)
		
	# Initiate Curl request and then return what we receive.
	def __process(self):
		self.curl.perform()
		return self.buffer.getvalue()
	
	# Reset buffer and curl.  Set curl options that are universal to all requests.
	def __reset_connection(self):
		if self.buffer: self.buffer.close() # Close the IO buffer if it exists.
		if self.curl: self.curl.close() # Close Curl handle if it exists.

		# Initialize handlers.
		self.curl = pycurl.Curl()
		self.buffer = StringIO.StringIO()

		# Setup Curl to use cookies and our StringIO buffer.
		self.curl.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
		self.curl.setopt(pycurl.COOKIEFILE, self.cookie_path)
		self.curl.setopt(pycurl.COOKIEJAR, self.cookie_path)
	
	# Build a request that can be used to call the MWES servlet.
	def __build_request_url(self, controller, action, paramaters):
		
		# URL encode paramaters if there are any. 
		paramaters_encoded = ''
		if paramaters:
			paramaters_encoded = urllib.urlencode(paramaters)
			
		return '%s/%s.srv?remoteAction=%s&%s' % (self.agent_url, controller, action, paramaters_encoded)
		
	# Make a request via the MWES servlet. Return JSON decoded output of servlet.
	def request(self, controller, action, paramaters):
		self.__reset_connection()
		self.curl.setopt(pycurl.URL, self.__build_request_url(controller, action, paramaters))
		return json.loads(self.__process())
	
	# Add a domain to MWES.
	def add_domain(self, domain_name):
		# Set paramaters for request and make the actual request.
		paramaters = { 'domain' : domain_name }
		result = self.request('Domains', 'add', paramaters) # JSON decode of request.

		# Return true if domain name was removed.
		return result['remoteActionResponse'] != 'failed'
	
	# Rename a domain in MWES. No rename function in MWES yet, so we'll do things the UNIX "rename" way.
	def rename_domain(self, domain_name_old, domain_name_new):	
		return (self.remove_domain(domain_name_old) and self.add_domain(domain_name_new))
	
	# Remove a domain from MWES.
	def remove_domain(self, domain_name):
		# Set paramaters for request and make the actual request.
		paramaters = { 'domain' : domain_name }
		result = self.request('Domains', 'remove', paramaters) # JSON decode of request.
		
		# Return true if domain name was removed.
		return result['remoteActionResponse'] != 'failed'
			
	# Check for the existence of a domain in MWES.
	def domain_exists(self, domain_name):
		# Set paramaters for request and make the actual request.
		paramaters = { 'domain' : domain_name }
		result = self.request('Domains', 'query', paramaters) # JSON decode of request.
		
		# Return true if domain name was returned.
		if result['remoteActionResponse'] != 'failed':
			return domain_name in result['domains']
	
	# Get a list containing all domain names in MWES.
	def get_all_domains(self):
		# Set paramaters for request and make the actual request.
		results = self.request('Domains', 'query', None) # JSON decode of request.
		
		# Return true if domain name was returned.
		if results['remoteActionResponse'] != 'failed':
			return results['domains']
	
	# Connect to MWES and login so we can store a session cookie.
	def connect(self, username, password):
		self.__reset_connection()
		
		# Set fields.
		login_fields = urllib.urlencode({'userid' : username, 'password' : password})
		self.curl.setopt(pycurl.POSTFIELDS, login_fields)
		self.curl.setopt(pycurl.URL, self.agent_url)
		
		# Process the actual request and return the response from MWES (full HTML page).
		result = self.__process()

		# HACK: Scrape the result for an error that only appears after a failed login.
		if '<span class="Error">UserID Password incorrect</span>' in result:
			# Login failed: fatal.
			print '[MWES] Your username or password is incorrect.'
			exit()

# This class essentially controls all synchronization.
class PleskMWESSync:
	
	plesk_agent = None
	mwes_control = None
	
	plesk_domain_list = []
	mailwasher_domain_list = []
	
	def __init__(self, plesk_agent, mwes_control):
		self.plesk_agent = plesk_agent
		self.mwes_control = mwes_control
		
		self.populate_domain_lists()
		
	def populate_domain_lists(self):
		self.plesk_domain_list = self.plesk_agent.get_all_domains()
		self.mailwasher_domain_list = self.mwes_control.get_all_domains()
	
	def for_addition(self):
		return list(set(self.plesk_domain_list).difference(set(self.mailwasher_domain_list)))
		
	def for_removal(self):
		return list(set(self.mailwasher_domain_list).difference(set(self.plesk_domain_list)))
		
## ESTABLISH CONTROLS.
######################
	
agent = PleskRPCAgent(Plesk.HostName, Plesk.Port, Plesk.Username, Plesk.Password)
mwc = MWESControl(MailWasher.HostName, MailWasher.Port, MailWasher.Username, MailWasher.Password)

## PROCESS COMMAND LINE ARGUMENTS.
##################################

# Sync MailWasher with Plesk.
if len(sys.argv) == 2 and sys.argv[1] == 'sync':
	
	# Get a list of domains to add and remove.
	sync = PleskMWESSync(agent, mwc)
	new_domains = sync.for_addition()
	old_domains = sync.for_removal()
	
	# If there is nothing to do, bail. No need to report anything, either.
	if not new_domains and not old_domains:
		print 'Plesk and MWES are synchronized.'
		exit()
		
	failed_domains = []
	
	# Add new domains.
	if new_domains:
		print 'Adding:'
	for domain_name in new_domains:
		if mwc.add_domain(domain_name):
			status = 'OK'
		else:
			status = 'FAIL'
			failed_domains.append(domain_name)
		print '\t%s [%s]' % (domain_name, status)
	
	# Remove old domains.
	if old_domains:
		print 'Removing:'
	for domain_name in old_domains:
		if mwc.remove_domain(domain_name):
			status = 'OK'
		else:
			status = 'FAIL'
			failed_domains.append(domain_name)
		print "\t%s [%s]" % (domain_name, status)
	
	Notifier.SynchronizationReport(new_domains, old_domains, failed_domains)
	exit()

# Create a domain in MWES.
if len(sys.argv) == 3 and sys.argv[1] == 'add-domain':
	if mwc.add_domain(sys.argv[2]):
		status = 'OK'
		Notifier.AddSuccess(sys.argv[2])
	else:
		status = 'FAIL'
		Notifier.AddFailure(sys.argv[2])
	print "Adding:\n\t%s [%s]" % (sys.argv[2], status)
	exit()

# Rename a domain in MWES.
if len(sys.argv) == 4 and sys.argv[1] == 'rename-domain':
	if mwc.rename_domain(sys.argv[2], sys.argv[3]):
		status = 'OK'
		Notifier.RenameSuccess(sys.argv[2], sys.argv[3])
	else:
		status = 'FAIL'
		Notifier.RenameFailure(sys.argv[2], sys.argv[3])
	print "Renaming:\n\t%s -> %s [%s]" % (sys.argv[2], sys.argv[3], status)
	exit()
	
# Delete a domain in MWES.
if len(sys.argv) == 3 and sys.argv[1] == 'remove-domain':
	if mwc.remove_domain(sys.argv[2]):
		status = 'OK'
		Notifier.RemoveSuccess(sys.argv[2])
	else:
		status = 'FAIL'
		Notifier.RemoveFailure(sys.argv[2])
	print "Removing:\n\t%s [%s]" % (sys.argv[2], status)
	exit()

# Display help information if we haven't done anything else.
print "To add or remove a single domain, use:"
print sys.argv[0], '<add-domain, rename-domain, remove-domain> <domain>'
print
print "To synchronize all MWES domains with Plesk, use:"
print sys.argv[0], '<sync>'
