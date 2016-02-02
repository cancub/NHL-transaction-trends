import datetime

class DateFormatter():

	def __init__(self, current_date):
		self.date = datetime.datetime.now(pytz.timezone('US/Eastern'))
		self.formatted_date = format_date()
		self.date_dict = make_date_dict()
	
	def format_date(self):

	    """
	    formatted date must be in the form of
	    YYYY-MM-DD
	    taking great care that the month and day are two digits long
	    i.e. 1998-09-02
	    """

	    year = self.date.year
	    month = self.date.month
	    if month < 10:
	        month = "0{}".format(month)
	    day = self.date.day
	    if day < 10:
	        day = "0{}".format(day)

	    # date_dict = {"day": day, "month": month, "year": year}

	    return "{0}-{1}-{2}".format(year,month,day)

	def make_date_dict(self):

	    year = self.date.year
	    month = self.date.month
	    day = self.date.day
	    hour = self.date.hour
	    minute = self.date.minute


	    date_dict = {"day": day, "month": month, "year": year, "hour":hour, "minute": minute}

	    return date_dict

	def time_difference(self, later_date, earlier_date,diff_type):


        later = datetime.datetime(int(later_date["year"]),int(later_date["month"]), int(later_date["day"]), 
            int(later_date["hour"]), int(later_date["minute"]))

        earlier = datetime.datetime(int(earlier_date["year"]), int(earlier_date["month"]), int(earlier_date["day"]),
            int(earlier_date["hour"]), int(earlier_date["minute"]))

        difference = later - earlier

        if diff_type == "minutes" :

            result = float(difference.seconds)/60

        elif diff_type == "hours":

            result = float(difference.seconds)/3600

        elif diff_type == "days":

            result = difference.days

        return result
