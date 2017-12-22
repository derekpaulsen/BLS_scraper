import re
from pathlib import Path
from typing import Iterator, List, Any
import requests
import json
################################## SOURCE FILES ##################################################
page = 'editted_BLS_page.txt' #page specifying formats for series
id_code_dir = './spec_files' 
code_files = list(Path(id_code_dir).iterdir())
###################################################################################################

class SubCode:
    def __init__(self, **kwargs):
        #may not be used for literals
        self.name =  kwargs.get('name', 'DEFAULT')

        #literals should always have this set to something
        self.value =  kwargs.get('value', None)
        self.literal = kwargs.get('literal', False)

        #may be a list if multi_src is True
        self.src =  kwargs.get('src', None)
        self.multi_src =  kwargs.get('multi_src', False)
        self.tuples = None
        
        if self.literal != (self.value != None):
            raise Exception("Literal subcode without value")

        if self.multi_src:
            self.src = []

    def validate(self):
        if self.multi_src:
            for f in self.src:
                with open(f , 'r') as ifs:
                    head = ifs.readline()
                    self.find_index(head, ifs.name)

        elif not self.literal:
            with open(self.src, 'r') as ifs:
                head = ifs.readline()
                self.find_index(head, self.src.name)
    
    def make_tuples(self):

        if self.multi_src:
            self.tuples = []
            for f in self.src:
                temp = self.read_sub_code_file(f)
                self.tuples.extend(temp)
    
        elif not self.literal:
            self.tuples = self.read_sub_code_file(self.src)                   


    @classmethod
    def find_index(cls, head, filename) -> tuple:
        '''
        returns a tuple containing the indicies of the code 
        :param head: the first line of the text file being parsed
        '''

        #filename is xx.industry.txt -> industry xx is the prefix
        category = re.search("\.(\w+)\.txt", filename, re.I).group(1)

        #Default case only two columns
        head = head.split('\t')
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
            if code == exact_match == None:
                print("ERROR: failure to determine CODE in %s" % filename)
            if opt_text == None:
                print("ERROR: failure to determine TEXT in %s" % filename)
            #Signal failure
            return None
    

   
    @staticmethod
    def search_head(head : list, regex) -> int:
        '''
        Determines the index of the column which matches the regex
        :return: index of the column
        '''


        matches = [i for i in range(len(head)) if regex.search(head[i]) != None]
        return matches[0] if len(matches) == 1 else None
        


    def read_sub_code_file(self, fp) -> List[tuple]:
        '''
        Creates a dictionary for the sub_code file which has keys = options
        and values = codes

        :param f: file that will be converted to a dictionary
        '''
        with open(fp, 'r') as f:
            file_list = []
            head = f.readline()
            indices = self.find_index(head, f.name)

            if indices == None:
                return []

            key_idx, val_idx = indices
            #iterate through the rows creating tuples of the text to code sub_code
            for line in f.readlines():
                line = line.split('\t')
                try:
                    file_list.append((line[key_idx], line[val_idx]))
                except:
                    if(len(line) > 1):
                        print("ERROR in %s parsing line: %s" %(f.name, " ".join(line))) 
                        
            
            #if there was no proper header
            if len(file_list[0][1]) == len(head[val_idx]):
                file_list.insert(0, (head[key_idx], head[val_idx]))
            
            return file_list


class SeriesBuilder(object):
    '''
    SeriesBuilder class is used for taking data parsed from the formatted
    BLS page and turning it into a multi layer dictionary which is then
    used in the SeriesIdGenerator class.
    '''

    global code_files
    #list of file objs
    class_files = code_files
    file_names = [f.name for f in code_files]

    def __init__(self, name : str , sub_codes : list) -> None:

        self.name: str = name
        self.prefix: str = self.check_prefix(sub_codes[0])
        self.sub_codes: List[Any] = sub_codes[1:]
    

    @classmethod
    def from_string(cls, info : str):
            '''
            Constructor which parses a segment of the formatted BLS page
            :param info: segment of the BLS page, containing series name and sub_codes
            '''
            #regex for a line in the format table
            code_regex = re.compile('(\w+?)\s+(\w+?)\s+(.+)')
            #line iterator
            itr = (x for x in info.split('\n'))
            series_name = cls.get_series_name(itr)
            sub_codes = []

            for line in itr:
                match = code_regex.search(line)

                #if match doesn't contain the sub_code
                if match == None:
                   continue

                sub_codes.append(cls.get_sub_code(match))
            
            return cls(series_name, sub_codes)


    @staticmethod
    def get_sub_code(match) -> str:
        '''
        Given the regex match, this method determines how it should be interpreted

        :param match: the regex match be processed
        :return: the code category
        '''

        #table value should be interpreted as a literal 
        if match.group(3).strip() == "DEFAULT" or match.group(3).strip() == "Prefix":
            sc = SubCode(value = match.group(2).strip(), name = match.group(3).strip(), literal = True) 
            return sc

        #list of sub_codeifiers
        elif '[' in match.group(3):
            line = match.group(3).strip()[1:-1]
            #split the line on ',' 
            names = [x.strip().lower() for x in line.split(',')]
            return  SubCode(name = names, multi_src = True)
        else:
            return SubCode(name = match.group(3).lower())


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
        self.find_sub_code_files()
        
        for sub_code in self.sub_codes:
            sub_code.validate()
            sub_code.make_tuples()
        
        return Series(self)
    
    @staticmethod
    def check_prefix(sc :SubCode) -> str:
        '''
        Helper method for __init__ which checks that the
        prefix is valid. 
        '''
        if sc.name != "Prefix" or len(sc.value) != 2:
            raise Exception("invalid prefix")
        else:
            return sc.value
        

    def find_sub_code_files(self) -> None:
        '''
        Checks to see that all of the files for creating the 
        series dictionary are in fact present.
        '''
        for sub_code in self.sub_codes:
            if sub_code.multi_src:
                for name in sub_code.name:
                    temp = self.find_file(name)
                    if temp != None:
                        sub_code.src.append(temp)

            elif not sub_code.literal:
                temp = self.find_file(sub_code.name)
                if temp != None:
                    sub_code.src = temp
                    

    def find_file(self, name: str):
         '''
         Search through all the files and return the file whose
         name matches the sub_code
         :return: the proper file object if found else None
         '''
         fname = "%s.%s.txt" % (self.prefix.lower(),  name.strip().lower())
         for f in SeriesBuilder.class_files:
            if fname in f.name:
                return f

         print("cannot find %s" % fname)
         return None
        
                        
    

    

    


class Series:

    def __init__(self, builder):
        self.name = builder.name
        self.prefix = builder.prefix
        self.sub_codes = builder.sub_codes




############################## MODULE INIT ####################################
def parse_page(BLS_page: str):
    '''
    :param BLS_page: a str with the name of the formatted page to be parsed
    '''
    with open(BLS_page, 'r') as infile:
            series = re.findall('\{.*?\}', infile.read(), re.S)
            #list contain series_builder objects
            series_builders = []
            for s in series:
                series_builders.append(SeriesBuilder.from_string(s))

            return series_builders



series_list = []

series_builders = parse_page(page)

for s in series_builders:
    series_list.append(s.build())


###############################################################################################


class SeriesRequest:
    header = {'Content-type': 'application/json'}
    def __init__(self, start_year = None, end_year = None):
        self.series_id = None
        self.start_year = start_year
        self.end_year = end_year
        self.request_data = {}
        self.response = None
        

    def send(self, site):
        '''
        send the request to the site
        '''
        
        self.request_data['startyear'] = self.start_year
        self.request_data['endyear'] = self.end_year
        self.request_data['seriesid'] = [self.series_id]
        self.request_data = json.dumps(self.request_data)

        self.response = requests.post(site, data = self.request_data, headers= self.header)
        self.response = json.loads(self.response.text)
        

    def write(self):
        with open(f"{self.series_id}-{self.start_year}-{self.end_year}.txt", 'w') as out:
            for datum in self.response['Results']['series'][0]['data']:
                year = datum['year']
                period = datum['period']
                value = datum['value']
                footnotes= ", ".join([s for s in datum['footnotes'] if len(s) > 1])
                out.write(f"{year}; {period}; {value}; {footnotes}\n")




class SeriesIdGenerator(object):
    '''
    This class does exactly what you would think. It generates a series ID
    '''
    global series_list
    #all of the series objects that were built during module init
    series_objs = series_list

    def __init__(self):
        self.ids_generated = []
    
    @staticmethod
    def get_opt(sub_code) -> str:
        #TODO allow the user to search options instead of just printing all of them out

        print(f"enter option for {sub_code.name} or 'exit'")
        for i in range(len(sub_code.tuples)):
            print("%d : %s" % (i, sub_code.tuples[i][0]))

        while 1:
            opt = input(">>> ")
            #input is a valid index
            if opt.isdigit() and 0 <= int(opt) < len(sub_code.tuples):
                return sub_code.tuples[int(opt)][1]

            elif opt == 'exit':
                raise SystemExit

            else:
                print(f"invalid option: {opt}")
                continue



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
        #TODO might want to make the prefix just another subcode
        id_parts = [series.prefix]
        #prompt user to select codes
        for sub_code in series.sub_codes:
            if sub_code.literal:
                id_parts.append(sub_code.value)
            else:
                id_parts.append(self.get_opt(sub_code))  

        completed_id = "".join(id_parts)
        self.ids_generated.append(completed_id)

        return completed_id


class BLSScraper(object):
    '''
    This is for API v1, which is the unregistered version, the number of requests per day is
    restricted to 25 per day and a 10 year range
    '''

    def __init__(self):
        #header is always the same
        self.SIDgen = SeriesIdGenerator()
        self.series_requests = []


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
            else:
                print(f"invalid option '{year}'")

        return years

    def make_series_request(self):
        '''
        Prompt the user for the time period and then some number of SeriesIds
        '''
        years = self.get_time_period()

        while 1:
            series_id = self.SIDgen.prompt_user()
            request = SeriesRequest(*years)
            request.series_id = series_id

            self.series_requests.append(request)
            print(f"Add another series id for time period {years[0]} to {years[1]}?(y/n)")
            opt = input(">>> ")
            if 'y' not in opt:
                break


    def send_requests(self):
        bls_site = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'
        for request in self.series_requests:
            request.send(bls_site)

            
    def write_responses(self):
        for series_request in self.series_requests:
            series_request.write()




    


