import json

class JSONTool():
	def __init__(self, infile, outfile):
		self.
		pass

	def print_json(self, json_object):
	    print json.dumps(json_object, indent=4, sort_keys=True) 
	    print "\n"

	def load_json_file(self, file_name):

	    data = None

	    try:
	        with open(file_name) as data_file:
	                data = json.load(data_file)
	    except:
	        pass

	    return data

	def write_json_file(self, transactions_dict, file_name):
	    with open(file_name,'w') as outfile:
	        json.dump(transactions_dict, outfile, indent=4, sort_keys=True)