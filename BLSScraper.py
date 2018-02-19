import re
from pathlib import Path
from typing import Iterator, List, Any
import requests
import json
from sys import stdout
################################## SOURCE FILES ##################################################
page = 'editted_BLS_page.txt' #page specifying formats for series
id_code_dir = './spec_files' 
code_files = list(Path(id_code_dir).iterdir())
#enter APIv2 key here if you want to use the APIv2
#else leave it as None
v2_key =None
###################################################################################################


class Restart(Exception):
    
    def __init__(self, message = None):
        super().__init__(message)


class SubCode:
    '''
    This class is used to store the information for the sub part of a series
    id. For example the industry code, etc.
    '''
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
    Series builders are a class for creating parsing the text files which contain
    the information generating series ids. 
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
    '''
    Series are simply a handle for information for generating a particular 
    series id
    '''
    def __init__(self, builder):
        self.name = builder.name
        self.prefix = builder.prefix
        self.sub_codes = builder.sub_codes

    #TODO add an __iter__ method



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
    '''
    This class contains all the information, which is collected from the user
    for sending a request to the BLS. Note that for simplicity of writing, only 
    one series id is contained in each SeriesRequest, despite the fact that
    it is possible to send multiple series id requests at once via the BLS API
    '''

    header = {'Content-type': 'application/json'}
    def __init__(self, series_id: str, years: tuple, comments: list):
        self.series_id = series_id 
        self.start_year = years[0]
        self.end_year = years[1]
        self.request_data = {}
        self._response = None
        self._comments = comments
        self._valid = False
        self._sent = False
        self._written = False

    def send(self, site: str, key = None) -> None:
        '''
        send the request to the site
        '''
        if not self._sent:
            #create json request
            self.request_data['startyear'] = self.start_year
            self.request_data['endyear'] = self.end_year
            self.request_data['seriesid'] = [self.series_id]
            if key != None:
                self.request_data['registrationkey'] = key
                
            self.request_data = json.dumps(self.request_data)
            
            self._response = requests.post(site, data = self.request_data, headers= self.header)
            self._response = json.loads(self._response.text)

            self._sent = True
            self.validate()
            return self._valid

    def write(self) -> None:
        '''
        write the data from the response to a text file in csv2 format
        '''
        try:
            if not self._written:
                
                with open(f"{self.series_id}-{self.start_year}-{self.end_year}.txt", 'w') as out:
                    #write comments
                    out.write("#%s\n" % self.series_id)
                    for comment in self._comments:
                        out.write("#%s\n" % comment)

                    #write the data
                    for datum in self._response['Results']['series'][0]['data']:
                        year = datum['year']
                        period = datum['period']
                        value = datum['value']
                        footnotes = ", ".join([s for s in datum['footnotes'] if len(s) > 1])
                        out.write(f"{year}; {period}; {value}; {footnotes}\n")

                    self._written = True

        except Exception as e:
            print(f'ERROR writing request {", ".join(self._comments)}')
            print(str(e))
            self._written = True


    def validate(self) -> None:
        try:
            self._valid = self._response['status'] == 'REQUEST_SUCCEEDED'
            self._comments.extend(self._response['message'])
        except Exception as e:
            #any exceptions during this checking will cause an exception during a 
            #write attempt, hence the response isn't valid for writing
            self._valid = False

        

    def print_res(self, stream = stdout):
        print(self._response, file = stream)

    def __str__(self) -> str:
        return f'{self._comments[0]}: {", ".join(self._comments[1:])}'
    
    @property
    def sent(self):
        return self._sent

    @property
    def written(self):
        return self._written
    
    @property
    def valid(self):
        return self._valid

    @property
    def comments(self):
        return self._comments

class SeriesIdGenerator(object):
    '''
    This class does exactly what you would think. It generates a series ID
    '''
    global series_list
    #all of the series objects that were built during module init
    series_objs = series_list

    def __init__(self):
        #list of id's generated, currently unused
        self.ids_generated = []
    
    
    def generate(self) -> tuple:
        '''
        prompt user to create a BLS information request return a series id
        '''
        #print all the series names
        print("Please select the series you wish to access")
        opt = self.prompt([s.name for s in self.series_objs])
        series = self.series_objs[opt]

        comments = [series.name]
        id_parts = [series.prefix]
        #prompt user to select codes
        for sub_code in series.sub_codes:
            if sub_code.literal:
                id_parts.append(sub_code.value)
            else:
                opt_str, opt_id = self.get_opt(sub_code)
                comments.append(opt_str)
                id_parts.append(opt_id)  
        
        #join all the id parts into on str
        completed_id = "".join(id_parts)
        self.ids_generated.append(completed_id)

        return (comments, completed_id)

    def get_opt(self, sub_code) -> tuple:

        option_names = [name for name, code in sub_code.tuples]
        print(f"(s)earch for options or print (a)ll for {sub_code.name.upper()}")
        opt = input('> ')
        indexes = None
        if 's' in opt:
            indexes = self.search(option_names)
        
        choice = self.prompt(option_names, indexes)
            
        return sub_code.tuples[choice]


    @classmethod
    def prompt(cls, options, indexes = None) -> int:
        #TODO add message about restart and search

        choice = None
        indexes = range(len(options)) if indexes == None else indexes

        for i in indexes:
            print('%d : %s' % (i, options[i]))

        while 1:
            choice = input('> ')
            if choice.isdigit() and int(choice) in indexes:
                return int(choice)

            #change search term
            elif 'search' in choice:
                indexes = cls.search(cls, options)
                return cls.prompt(options, indexes)
            elif 'restart' in choice:
                raise Restart
            else:
                print(f"invalid option: {choice}")

    def search(self, options):
        '''
        prompt user for search term and search options for the matches
        return a list in indexes which the pattern is contained
        '''
        r = range(len(options))
        print('enter search option')
        while 1:
            pattern = input('? ')
            matches =  [i for i in r if pattern in options[i]]
            if len(matches) == 0:
                print(f"No matches found for {pattern}")
            else:
                return matches

class BLSScraper(object):
    '''
    This is for API v1, which is the unregistered version, the number of requests per day is
    restricted to 25 per day and a 10 year range
    '''
    global v2_key
    api_key = v2_key
    def __init__(self):
        #header is always the same
        self.SIDgen = SeriesIdGenerator()
        self.series_requests = []
        self._APIV2 = self.api_key != None
    
    def main(self):
        print('Welcome to the BLS Scraper!')
        print("Commands are: 'send', 'write', 'new', 'exit', 'show', 'delete', 'help'")
        print('please enter a command: ')
        while 1:
            try:
                opt = input('> ')
                if 'send' in opt:
                    self.send_requests()    

                elif 'write' in opt:
                    self.write_responses()

                elif 'new' in opt:
                    self.make_series_request()
                
                elif 'help' in opt:
                    self.help()
                
                elif 'show' in opt:
                    self.show_requests()

                elif 'delete' in opt:
                    self.delete_request()

                elif 'exit' in opt:
                    print('Exiting...')
                    raise SystemExit
                
                else:
                    print(f'invalid command {opt}')

                print('please enter a command: ')
                opt = ''
            #the restart the command
            except Restart:
                print('Restarting...')
                print("Commands are: 'send', 'write', 'new request', 'exit'")
                print('please enter a command: ')
                continue

        


    def make_series_request(self):
        '''
        Prompt the user for the time period and then some number of SeriesIds
        '''
        years = self.get_time_period()
        done = False
        while not done:
            comments, series_id = self.SIDgen.generate()
            request = SeriesRequest(series_id = series_id, years = years, comments = comments)
            request.series_id = series_id

            self.series_requests.append(request)

            print(f"Add another series id for time period {years[0]} to {years[1]}?(y/n)")
            done = 'y' not in input('> ')

    def get_time_period(self) -> tuple:
        '''
        Prompt user for time period
        '''
        #TODO check what the proper data range is
        minyear = 1900
        maxyear = 2017

        max_range = 9 if not self._APIV2 else 19
        #TODO check that this is correct>-------^^
        years = []
        while len(years) < 2:
            print(f"Enter start year between {minyear} and {maxyear}")

            while True:
                year = input('> ')
                if not year.isdigit():
                    print(f"invalid option '{year}'")

                elif minyear <= int(year) <= maxyear:
                    years.append(year)
                    minyear = int(year)
                    maxyear = int(year) + max_range
                    break
                else:
                    print(f"invalid option '{year}'")

        return years


    def send_requests(self):
        bls_site = 'https://api.bls.gov/publicAPI/v1/timeseries/data/' 
        if self._APIV2:
            bls_site = 'https://api.bls.gov/publicAPI/v2/timeseries/data/' 
            
        for request in self.series_requests:
            request.send(bls_site, self.api_key)
            #if request didn't return a valid response
            if not request.valid:
                print(f'Request failed to send: {", ".join(request.comments)}')
                opt = input('print json response?(y/n): ')
                if 'y' in opt:
                    request.print_res()
            

    def write_responses(self):

        for series_request in filter(lambda x: x.sent, self.series_requests):
            if series_request.valid:
                series_request.write()
            else:
                print('BLS returned error for series request:', end = '')
                print('\n\t'.join(series_request.comments()))

    @staticmethod
    def help():
        help_str = '''
        'exit': exit the program immediately doesn't write or save any data
        'new request': create a new request to send to the BLS
        'restart': return to the main menu 
        'search': search available options for sub codes, hitting return with no input will print all options
        'send': send the requests to the BLS
        'write': write all responses
        '''
        print(help_str)
    
    def show_requests(self):
        '''
        show the requests currently in the scraper
        '''
        if len(self.series_requests) == 0:
            print('no requests')
        else:
            print('\nUnsent Requests:\n')
            for request in filter(lambda x: not x.sent, self.series_requests):
                
                print(str(request))

            print('\nSent Requests:\n')
            for request in filter(lambda x: x.sent, self.series_requests):
                print(str(request))
            
            
        
    def delete_request(self):
        '''
        prompt user to delete request from the options
        '''
        print("Select a request to delete or 'restart' to return the main menu")
        strs = [str(r) for r in self.series_requests]
        opt = SeriesIdGenerator.prompt(strs)
        del self.series_requests[opt]

    




if __name__ == '__main__':
    bs = BLSScraper()
    bs.main()

