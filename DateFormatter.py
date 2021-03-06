import datetime
import pytz

class DateFormatter():

    def __init__(self):
        self.my_tz = pytz.timezone("Canada/Eastern")
        self.date = self.my_tz.localize(datetime.datetime.now())
        self.formatted_date = self.format_date()
        self.date_dict = self.make_date_dict()
    
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

    def make_date_dict(self, datetime_object = None):

        if not datetime_object:

            year = self.date.year
            month = self.date.month
            day = self.date.day
            hour = self.date.hour
            minute = self.date.minute

        else:

            year = datetime_object.year
            month = datetime_object.month
            day = datetime_object.day
            hour = datetime_object.hour
            minute = datetime_object.minute


        date_dict = {"day": day, "month": month, "year": year, "hour":hour, "minute": minute}

        return date_dict

    def time_difference(self, date_dict,diff_type):

        earlier = self.make_datetime(date_dict)

        difference = self.date - earlier

        if diff_type == "minutes" :

            result = float(difference.seconds)/60

        elif diff_type == "hours":

            result = float(difference.seconds)/3600

        elif diff_type == "days":

            result = difference.days

        return result

    def make_datetime(self,date_dict):
        return self.my_tz.localize(datetime.datetime(int(date_dict["year"]), int(date_dict["month"]), int(date_dict["day"]),
            int(date_dict["hour"]), int(date_dict["minute"])))

    def now(self):
        return self.my_tz.localize(datetime.datetime.now())

    def update(self):
        self.__init__()
