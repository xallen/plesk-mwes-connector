#!/usr/bin/env python

import os, sys, tempfile, pycurl, StringIO, smtplib, xml.dom.minidom, re, sqlite3
from subprocess import Popen, PIPE
from email.mime.text import MIMEText

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
	SQLiteDB = '/opt/mwes/mwes.db'

class Plesk:
	HostName = 'localhost'
	Port = '8443'
	Username = 'admin'
	Password = 'password'

# END EDIT. It would pay to leave everything below alone.
###############################################################################

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
		message = MIMEText('Added "%s" to MailWasher.' % (domain_name))
		message['Subject'] = '%s Added "%s" to MailWasher.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def AddFailure(domain_name):
		message = MIMEText('Failed to add "%s" to MailWasher. Please resolve this issue manually.' % (domain_name))
		message['Subject'] = '%s Failed to add "%s" to MailWasher.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def RemoveSuccess(domain_name):
		message = MIMEText('Removed "%s" from MailWasher.' % (domain_name))
		message['Subject'] = '%s Removed "%s" from MailWasher.' % (Notifier.MailTag, domain_name)
		Notifier.Send(message)
		
	@staticmethod
	def RemoveFailure(domain_name):
		message = MIMEText('Failed to remove "%s" from MailWasher. Please resolve this issue manually.' % (domain_name))
		message['Subject'] = '%s Failed to remove "%s" from MailWasher.' % (Notifier.MailTag, domain_name)
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
		
		report += "\n\n If you have received this report then Plesk and MWES have become unsynchronized. Are your Plesk events bound correctly?"
		
		message = MIMEText(report)
		message['Subject'] = '%s Synchronization Report' % (Notifier.MailTag)
		Notifier.Send(message)

		
class PleskRPCError(Exception):

	def __init__(self, error_code, error_text):
		self.error_code = error_code
		self.error_text = error_text
		
	def __str__(self):
		return '[%s] %s' % (self.error_code, self.error_text)

		
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

	def check_response_status(self): 
		# Parse buffer as XML.
		dom = xml.dom.minidom.parseString(self.buffer.getvalue())
		# If the system element exists we have a problem, but we'll check for an error specifically anyway.
		system_response = dom.getElementsByTagName('system')
		if len(system_response) > 0:
			error_code = system_response[0].getElementsByTagName('errcode')[0].childNodes[0].data
			error_text = system_response[0].getElementsByTagName('errtext')[0].childNodes[0].data
			raise PleskRPCError(error_code, error_text)
		
	def reset_buffer(self):
		# Destroy buffer if it exists, and release memory.
		if self.buffer: self.buffer.close()
		
		self.buffer = StringIO.StringIO()
		
		# Let Curl know where it is to write received data.
		self.curl.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
		
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
		
	def domains(self):
		packet = '<packet version="1.5.2.0"><domain><get><filter /><dataset><gen_info /></dataset></get></domain></packet>'

		# Send packet and get XML DOM response.
		dom = self.process(packet)
		
		domains = []
		for domain in dom.getElementsByTagName('name'):
			domains.append(str(domain.childNodes[0].data)) # Convert from Unicode to str.
		
		return sorted(domains)
	
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
		
	def get_all_domains(self):
		return sorted(agent.domains() + agent.subdomains() + agent.domain_aliases())

		
# This control handles MailWasher operations. Adding/Removing domains is done via Curl for instantaneous effect. Queries
# for domain existence and enumeration are done via a direct interface with MWES's SQLite database.
class MWESControl:
	
	# Web-based hook.
	buffer = None
	curl = None

	# SQLite-based hook.
	connection = None
	cursor = None
	
	agent_url = '' # URL of MailWasher.
	
	def __init__(self, hostname, port):
		
		# Store 
		self.agent_url = 'http://%s:%s/' % (hostname, port)
		
		# We need a cookie for MailWasher.
		self.cookie_fd, self.cookie_path = tempfile.mkstemp('-mwc')
		
		# Connect to SQLite interface.
		self.sql_connect()
		
		# Find the MailWasher username and password via SQL.
		username, password = self.get_web_admin_info()
		
		# Connect to web interface.
		self.web_connect(username, password)

	# Initiate Curl request and then return what we receive.
	def process(self):
		self.curl.perform()
		return self.buffer.getvalue()
	
	# Reset Curl and our StringIO buffer between requests.
	def _web_reset(self):
		if self.buffer: self.buffer.close() # Close the IO buffer if it exists.
		if self.curl: self.curl.close() # Close Curl handle if it exists.

		# Initialize handlers.
		self.curl = pycurl.Curl()
		self.buffer = StringIO.StringIO()

		# Setup Curl to use cookies and our StringIO buffer.
		self.curl.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
		self.curl.setopt(pycurl.COOKIEFILE, self.cookie_path)
		self.curl.setopt(pycurl.COOKIEJAR, self.cookie_path)
	
	def add_domain(self, domain_name):
		
		# Do we even need to remove the domain?
		if self.domain_exists(domain_name):
			return 1
			
		self._web_reset()
		new_domain_post_data = 'NewDomain=%s' % (domain_name)
		self.curl.setopt(pycurl.POSTFIELDS, new_domain_post_data)
		self.curl.setopt(pycurl.URL, self.agent_url + 'Domains.srv')
		result = self.process()
		return ('<td>' + domain_name + '</td>' in result)
		
	def remove_domain(self, domain_name):
	
		# Do we even need to remove the domain?
		if not self.domain_exists(domain_name):
			return 1
	
		self._web_reset()
		remove_url = '%sDomains.srv?delete=%s' % (self.agent_url, domain_name)
		self.curl.setopt(pycurl.URL, remove_url)
		result = self.process()
		return (not '<td>' + domain_name + '</td>' in result)
	
	def domain_exists(self, domain_name):
		domain = (domain_name, )
		self.cursor.execute('select domain from domains where domain = ? limit 1;', domain)
		return (self.cursor.fetchone())
			
	def get_all_domains(self):
		results = self.cursor.execute('select * from domains order by domain;')
		domains = []
		for domain in results:
			domains.append(str(domain[1])) # Convert from Unicode to str.
		return domains
	
	def sql_connect(self):
		# Connect to SQLite DB.
		self.connection = sqlite3.connect(MailWasher.SQLiteDB)
		self.cursor = self.connection.cursor()
		
	def get_web_admin_info(self):
		username = None
		password = None
		result = self.cursor.execute('select name, value from configure where name = "admin_username" or name = "admin_password";')
		for row in result:
			if row[0] == 'admin_username': username = str(row[1]) # Unicode to string for both.
			if row[0] == 'admin_password': password = str(row[1])
		return (username, password)
	
	def web_connect(self, username, password):
		self._web_reset()
		
		login_post_data = 'userid=%s&password=%s' % (username, password)
		self.curl.setopt(pycurl.POSTFIELDS, login_post_data)
		self.curl.setopt(pycurl.URL, self.agent_url)
		result = self.process()

		if '<span class="Error">UserID Password incorrect</span>' in result:
			print '[MAILWASHER] Your username or password is wrong.'
			exit()


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
		

# Establish our Plesk and MailWasher controls.		
agent = PleskRPCAgent(Plesk.HostName, Plesk.Port, Plesk.Username, Plesk.Password)
mwc = MWESControl(MailWasher.HostName, MailWasher.Port)

# Sync MailWasher with Plesk.
if len(sys.argv) == 2 and sys.argv[1] == 'sync':
	
	# Get a list of domains to add and remove.
	sync = PleskMWESSync(agent, mwc)
	new_domains = sync.for_addition()
	old_domains = sync.for_removal()
	
	# If there is nothing to do, bail. No need to report anything, either.
	if not new_domains and not old_domains:
		print 'Plesk and MailWasher are synchronized.'
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

# Create a domain in MailWasher.
if len(sys.argv) == 3 and sys.argv[1] == 'add-domain':
	if mwc.add_domain(sys.argv[2]):
		status = 'OK'
		Notifier.AddSuccess(sys.argv[2])
	else:
		status = 'FAIL'
		Notifier.AddFailure(sys.argv[2])
	print "Adding:\n\t%s [%s]" % (sys.argv[2], status)
	exit()

# Delete a domain in MailWasher.
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
print sys.argv[0], '<add-domain,remove-domain> <domain>'
print
print "To synchronize all MailWasher domains with Plesk, use:"
print sys.argv[0], '<sync>'
