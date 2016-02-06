import email.message

class EmailTool():
	def __init__(self):
		pass

	def send_email(self,notes_to_send):
	    print "Preparing email"
	    m = email.message.Message()
	    m['From'] = config.CONFIG["email"]["address"]
	    m['To'] = config.CONFIG["email"]["address"]
	    m['Subject'] = "Notable player transactions"

	    header = "Notes\n---------------------------------------\n"

	    my_payload = get_email_string(notes_to_send)

	    m.set_payload(my_payload)

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

	def get_email_string(self, notes):
	    """
	    notes format:
	    {
	        <player name>: {
	            "note": <player note>,
	            "verdict": <"add"/"drop">
	            "leagues": {
	                <league name>: <link>,
	                <league name>: <link>
	            }
	        }
	    }
	    """

	    # print "Formulating email"



	    email_string = []

	    for player in notes:

	        print_json(notes[player])
	        

	        player_string = []
	        # print player
	        # print_json(notes[player])
	        player_string.append("\n\nRecommendation for {}:\n\n".format(player)) 
	        player_string.append("Today's stats:\nAdds: {0}, Drops: {1}\n".format(notes[player]["stats"]["adds"],
	            notes[player]["stats"]["drops"]))   
	        player_string.append("Action: {}\n\n".format(notes[player]["verdict"]))

	        leagues = []
	        for league in notes[player]["leagues"]:
	            leagues.append("{0}: {1}".format(league,notes[player]["leagues"][league]))

	        player_string.append("Leagues:\n{}\n".format("\n".join(leagues)))
	        player_string.append("Rotowire notes:\n{}\n\n".format(notes[player]["note"]))

	        email_string.append("".join(player_string))

	    return "------------------------------------------------".join(email_string)