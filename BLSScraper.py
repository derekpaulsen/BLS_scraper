import re
from sys import argv
from pathlib import Path
from pprint import PrettyPrinter
from collections import OrderedDict
from typing import *
import shelve
import requests
import json
################################## MODULE INIT ##################################################
shelf_name = "series_shelf"
page = None
spec_dir = None
files = []

###################################################################################################

class SeriesBuilder(object):
    '''
    SeriesBuilder class is used for taking data parsed from the formatted
    BLS page and turning it into a multi layer dictionary which is then
    used in the SeriesIdGenerator class.
    '''
    #NOTE this class should never be instantiated unless running the main method of this module.

    global files
    #list of file objs
    class_files = files
    file_names = [f.name for f in files]

    def __init__(self, name : str , specs : list) -> None:

        self.name: str = name
        self.prefix: str = self.check_prefix(specs[0])
        self.specs: List[Any] = specs[1:]
        self.files: List[Any] = []
        self.series_map: OrderedDict = OrderedDict()
    

    @classmethod
    def from_string(cls, info : str):
            '''
            Constructor which parses a segment of the formatted BLS page
            :param info: segment of the BLS page, containing series name and specs
            '''
            #regex for a line in the format table
            find_code = re.compile('(\w+?)\s+(\w+?)\s+(.+)')
            #line iterator
            itr = (x for x in info.split('\n'))
            series_name = cls.get_series_name(itr)
            sub_codes = []

            for line in itr:
                match = find_code.search(line)

                #if match doesn't contain the spec
                if match == None:
                   continue
                #else parse spec
                else:
                    sub_codes.append(cls.get_spec(match))
            
            return cls(series_name, sub_codes)


    @staticmethod
    def get_spec(match) -> str:
        '''
        Given the regex match, this method determines how it should be interpreted
        Literals:
            if the third column specifies that the segment should be the same 
            for all series generated, return '$' + second column
        Lists:
            if one id segment may contain a code from multiple different code categories
            it returns a list of the categories
        Else:
            just the category

        :param match: the regex match be processed
        :return: the code category
        '''

        #table value should be interpreted as a literal 
        if match.group(3).strip() == "DEFAULT" or match.group(3).strip() == "Prefix":
            #literals have a '$' 
            return "$" + match.group(2).strip()

        #list of specifiers
        elif '[' in match.group(3):
            line = match.group(3).strip()[1:-1]
            #split the line on ',' 
            return[x.strip().lower() for x in line.split(',')]
        
        #return specifier
        else:
            return match.group(3).lower()


    @staticmethod
    def get_series_name(itr : Iterator[str]) -> str:
        '''
        Searchs through the raw string until it finds the first line longer
        that 5 chars, which should be the series name if it is formatted properly

        :return: the series name
        '''
        while 1:        
            series_name = next(itr)
            if len(series_name) > 5:
                return series_name


    def build(self) -> dict:
        '''
        Process the data to allow to be passed into a Series object constuctor 
        '''
        self.check_series()
        self.check_file_format(self.files)
        
        self.series_map['prefix'] = self.prefix
        for i in range(len(self.files)):
            key = self.specs[i] if type(self.specs[i]) == str else "/".join(self.specs[i])
            f = self.files[i]
            if type(f) == str:
                self.series_map[f] = f[1:]
            else:
                self.series_map[key] = self.spec_file_to_dict(f)

        return Series(self)
    
    @staticmethod
    def check_prefix(pre :str) -> str:
        '''
        Helper method for __init__ which checks that the
        prefix is valid. NOTE: if the prefix is not valid, to_map
        will fail and hence the series data will not be converted to a map
        '''
        if '$' not in pre or len(pre) != 3:
            raise RuntimeError("invalid prefix %s" % pre)
        else:
            return pre[1:]
        

    def check_series(self) -> None:
        '''
        Checks to see that all of the files for creating the 
        series dictionary are in fact present.
        '''
        for spec in self.specs:
            if type(spec) == list:
                fl = []
                for s in spec:
                    temp = self.find_file(s)
                    if temp != None:
                        fl.append(temp)

                self.files.append(fl)
              
            elif '$' in spec:
                self.files.append(spec)

            else:
                temp = self.find_file(spec)
                if temp != None:
                    self.files.append(temp)


    def find_file(self, spec):
         '''
         Search through all the files and return the file whose
         name matches the spec
         :return: the proper file object if found else None
         '''
         fname = "%s.%s.txt" % (self.prefix.lower(),  spec.strip().lower())
         for f in SeriesBuilder.class_files:
            if fname in f.name:
                return f

         print("cannot find %s" % fname)
         return None
        
                        
    @classmethod
    def check_file_format(cls, files) -> None:
        '''
        Goes through all the files which are necessary for create the series ID
        and ensures that they can be parsed. prints warning messages if errors or 
        ambiguities occur.
        This method was implemented as a classmethod to allow for recursive calls
        when files contains a list.
        '''
        for f in files:
            if type(f) == str:
                pass
            elif type(f) == list:
                cls.check_file_format(f)
            else:
                with f.open('r', errors = 'replace') as t:
                    cls.find_index(t.readlines()[0], f.name)
    
    @staticmethod
    def search_head(head : list, regex) -> int:
        '''
        Determines the index of the column which matches the regex

        :return: index of the column
        '''
        #number of the matches
        match_cnt= 0
        #index of match
        idx = None
        for i in range(len(head)):
            elem = head[i]
            match = regex.search(elem)
            if match != None:
                idx = i
                match_cnt += 1
        
        if match_cnt == 1:
            return idx
        #if nothing matches or more than one matches return none
        else:
            return None

    @classmethod
    def find_index(cls, head : str, filename) -> tuple:
        '''
        returns a tuple containing the indicies of the code 
        :param head: the first line of the text file being parsed
        '''
        #filename is xx.industry.txt -> industry xx is the prefix
        category = re.search("\.(\w+)\.txt", filename, re.I).group(1)

        #Default case only two columns
        head = head.lower().split('\t')
        if len(head) == 2:
            return (1,0)

        #search for indices of columns
        exact_match = cls.search_head(head, re.compile(category + ".*code", re.I))
        code = cls.search_head(head, re.compile("code", re.I))
        opt_text = cls.search_head(head, re.compile("text|name|title", re.I))
        
        #exact match for code header and option text found
        if exact_match != None and opt_text != None:
            return (opt_text, exact_match)
        #code and option text found
        elif code != None and opt_text != None:
            return (opt_text, code)
        else:
            #debug methods, if the program cannot determine a column
            if code == None and exact_match == None:
                print("ERROR: failure to determine CODE in %s" % filename)
            if opt_text == None:
                print("ERROR: failure to determine TEXT in %s" % filename)
            #Signal failure
            return None
        

    def spec_file_to_dict(self, fp) -> dict:
        '''
        Creates a dictionary for the spec file which has keys = options
        and values = codes

        :param f: file that will be converted to a dictionary
        '''
        #if a file is passed in combine all into one dictionary
        if type(fp) == list:
            dlist = [self.spec_file_to_dict(f) for f in fp]
            d = {}
            for i in dlist:
                d.update(i)
            return d
        
        #
        with open(fp, 'r') as f:
            file_list = []
            lines = f.readlines()
            head = lines[0]
            lines = lines[1:]

            indices = self.find_index(head, f.name)
            if indices == None:
                return []

            key_idx, val_idx = indices
            #iterate through the rows creating tuples of the text to code spec
            for l in lines:
                x = l.split('\t')
                try:
                    file_list.append((x[key_idx], x[val_idx]))
                except:
                    if(len(x) > 1):
                        print("ERROR in %s parsing line: %s" %(f.name, " ".join(x))) 
                        
            
            head = head.split('\t')
            #if there was no proper header
            if len(file_list[0][1]) == len(head[val_idx]):
                file_list.insert(0, (head[key_idx], head[val_idx]))
            
            return dict(file_list)



class Series:

    def __init__(self, builder):
        self.name = builder.name
        self.prefix = builder.prefix
        self.series_map = builder.series_map




###############################################################################################
############################## Build Series from raw data ####################################
def parse_page(BLS_page: str):
    '''
    :param BLS_page: a str with the name of the formatted page to be parsed
    '''
    with open(BLS_page, 'r') as infile:
            series = re.findall('\{.*?\}', infile.read(), re.S)
            #list contain series objects
            series_builders = []
            for s in series:
                series_builders.append(SeriesBuilder.from_string(s))

            return series_builders

series_list = []
try:
    shelf = shelve.open(shelf_name)
    series_list = shelf['series_list']

except KeyError:
    if __name__ == "__main__":
        '''
        Main method for the module, creates the master_map.txt
        '''
        if len(argv) != 3:
            print("Useage: python3 code_table_scraper.py <BLS format file> <input directory>")
            raise SystemExit

        name, page, directory= argv
        spec_dir = Path(directory)
        files += list(spec_dir.iterdir())

        series_builders = parse_page(page)

        for s in series_builders:
            series_list.append(s.build())

        shelf['series_list'] = series_list
        shelf.close()

    else:
        print("""
        Unable to find %s. 
        Run main method in SeriesIdGenerator.py with proper files to create %s
        """ % (shelf_name, shelf_name))
        raise SystemExit



###############################################################################################


class SeriesIdGenerator(object):
    '''
    This class does exactly what you would think. It generates a series ID
    '''
    series_objs = series_list

    def __init__(self):
        self.ids_generated = []
    
    @staticmethod
    def get_opt(category_name :str, opt_dict : dict) -> str:
        if type(opt_dict) == str:
            return opt_dict
        keys = list(opt_dict.keys())
        print(f"enter option for {category_name} or 'exit'")
        for t in enumerate(keys):
            print("%d : %s" % t)

        key = None
        while 1:
            opt = input(">>> ")
            #input is a valid index
            if opt.isdigit() and 0 <= int(opt) < len(keys):
                key = keys[int(opt)]
                break
            elif opt == 'exit':
                raise SystemExit
            else:
                print(f"invalid option: {opt}")
                continue

        return opt_dict[key]


    def prompt_user(self):
        series = None

        #print all the series names
        print("Please select the series you wish to access, or 'exit'")
        for t in enumerate([s.name for s in self.series_objs]):
            print("%d : %s" % t)
        while 1:
            opt = input(">>> ")
            #input is a valid index
            if opt.isdigit() and 0 <= int(opt) < len(self.series_objs):
                series = self.series_objs[int(opt)]
                break
            elif opt == 'exit':
                raise SystemExit
            else:
                print(f"invalid option: {opt}")
                continue

        id_parts = []
        #prompt user to select codes
        for name, d in series.series_map.items():
          id_parts.append(self.get_opt(name, d))  

        completed_id = "".join(id_parts)
        self.ids_generated.append(completed_id)
        #return completed id
        return completed_id


class BLSScraper(object):
    '''
    This is for API v1, which is the unregistered version, the number of requests per day is
    restricted to 25 per day and a 10 year range
    '''

    def __init__(self):
        self.SIDgen = SeriesIdGenerator()
        self.json_requests = []
        self.json_responses = None




    @staticmethod
    def get_time_period(start = 1900):
        '''
        Prompt user for time period
        '''
        #TODO check what the proper data range is
        minyear = 1900
        maxyear = 2017
        print(f"Enter start year between {minyear} and {maxyear}")
        years = []
        while len(years) < 1:
            year = input(">>> ")
            if not year.isdigit():
                print(f"invalid option '{year}'")
            elif minyear <= int(year) <= maxyear:
                years.append(year)
                minyear = int(year)
                
        print(f"Enter end year between {minyear} and {minyear + 10}")
        while len(years) < 2:
            year = input(">>> ")
            if not year.isdigit():
                print(f"invalid option '{year}'")
            elif minyear <= int(year) <= maxyear:
                years.append(year)
                
        return tuple(years)


    def make_json_request(self):
        '''
        Prompt the user for the time period and then some number of SeriesIds
        '''
        request_dict = {}
        years = self.get_time_period()
        request_dict['startyear'] = years[0]
        request_dict['endyear'] = years[1]
        request_dict['seriesid'] = []

        while 1:
            series_id = self.SIDgen.prompt_user()
            request_dict['seriesid'].append(series_id)
            if len(request_dict['seriesid']) >= 25:
                break
            
            print("Add another series id?(y/n)")
            opt = input(">>> ")
            if 'y' not in opt:
                break


        request = json.dumps(request_dict)
        self.json_requests.append((request, years))


    def send_requests(self):
        bls_site = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'
        header = {'Content-type': 'application/json'}
        self.json_responses = []

        for request, years in self.json_requests:
            res = requests.post( bls_site, data=request, headers=header)
            self.json_responses.append((json.loads(res.text), years))

            
        
    def write_responses(self):
        for data, years in self.json_responses:
            SID = data['Results']['series'][0]['seriesID']
            with open(f"{SID}-{years[0]}-{years[1]}.txt", 'w') as out:
                for datum in data['Results']['series'][0]['data']:
                    year = datum['year']
                    period = datum['period']
                    value = datum['value']
                    footnotes= ", ".join([s for s in datum['footnotes'] if len(s) > 1])
                    out.write(f"{year}; {period}; value; {footnotes}\n")
                




    


