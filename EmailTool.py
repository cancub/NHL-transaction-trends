import email.message
import config, smtplib

class EmailTool():
	def __init__(self):
		pass

	def send_email(self,payload):
	    print "Preparing email"
	    m = email.message.Message()
	    m['From'] = config.CONFIG["email"]["address"]
	    m['To'] = config.CONFIG["email"]["address"]
	    m['Subject'] = "Notable player transactions"

	    header = "Notes\n---------------------------------------\n"

	    m.set_payload(payload)

	    try:
	        # print("trying host and port...")

	        smtpObj = smtplib.SMTP_SSL('smtp.gmail.com', 465)
	        smtpObj.login("alfred.e.kenny@gmail.com", config.CONFIG["email"]["app_pw"])

	        # print("sending mail...")

	        smtpObj.sendmail(config.CONFIG["email"]["address"], 
	            config.CONFIG["email"]["address"], m.as_string())

	        # print("Succesfully sent email")

	    except smtplib.SMTPException:
	        print("Error: unable to send email")
	        import traceback
	        traceback.print_exc()