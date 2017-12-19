# BLS-Scraper
IMPORTANT
This script uses the unregistered API v1 for US BLS, which means that it is restricted to 10 year
intervals and 25 requests daily.


This script does decent number of things
1. read through the editted_BLS_page.txt and determines the format of each of series
(a few are not included due to not being able to find the data to make the ids).
2. check that all the text files which it expects to be there are there.
3. check that all files can be parsed properly based on the rather simple regular expresssions
4. finally it parses all the files and create an OrderedDict for each series for all the subcodes
It then caches all of these objects a python shelve.

5. BLSScaper class can then be used to prompt the user to create json requests to send to BLS
6. send those requests to the BLS
7. print out all the results in text files with csv2 format


NOTE
This is intended to be run out of an interpreter. To do this the main method in BLSScraper.py must be run 
with commandline arguments to create python shelve db to store all of the Series objects. On that note, 
you need to use the commands in this order

from Series import Series
from BLSScraper import *

to run this in the python3 interpreter

There are over 100 text files that this parses, chances are that some of the series ID's created
won't be valid, as these issues become apparent I will be updating the files as need to fix issues.
Additionally there are some vaild seriesIDs which the BLS may not have information for the requested time 
period.

