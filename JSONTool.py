import json

class JSONTool():
	def __init__(self, filename):
		self.filename = filename

	def print_json(self, json_object):
	    print json.dumps(json_object, indent=4, sort_keys=True) 
	    print "\n"

	def load_file(self):

	    data = None

	    try:
	        with open(self.filename) as data_file:
	            data = json.load(data_file)
	    except:
	        pass

	    return data

	def write_file(self, transactions_dict):
	    with open(self.filename,'w') as outfile:
	        json.dump(transactions_dict, outfile, indent=4, sort_keys=True)