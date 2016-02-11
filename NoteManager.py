
class NoteManager():

	def __init__(self):
		self.site = "rotoworld.com"
		self.notes_on_hold = []

	def get_player_notes(self, player_name):
	    # Obtain notes from player on rotoworld.com

	    # print "Searching for notes from rotoworld"

	    name_parts = re.split('\W+', player_name)
	    google_search = "http://www.google.com/search?start=0&num=1&q={0}+site:{1}".format(
	        "+".join(name_parts), self.site)
	    r = requests.get(google_search)
	    soup = BeautifulSoup(r.content,'html.parser')
	    link = soup.find("h3",{"class":"r"})
	    hlink = link.find("a")["href"]
	    search_link = str(re.split("=",re.split("&",hlink)[0])[1])
	    r = requests.get(search_link)
	    soup = BeautifulSoup(r.content,'html.parser')
	    info = soup.find("div",{"class":"playernews"})
	    report = info.find("div",{"class":"report"})
	    impact = info.find("div",{"class":"impact"})
	    note = report.contents[0] + " " + impact.contents[0]

	    return note

	def store_note(self,note):
		self.notes_on_hold.append(note)