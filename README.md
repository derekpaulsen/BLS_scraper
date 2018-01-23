# BLS-Scraper
This script allows you to use either to API v2 or API v1 for the BLS public data API

Getting started
=====
If you wish to use the APIv2 go into the source file and enter your registration key as a string
for the variable v2_key, otherwise leave this a None. The script will check to see if the key 
has been written and use the correct format for requests.

Note, the script will generate and send requests which that BLS may not have data for. 
Current it will just print a csv2 file which just contains the header of the failed request.

Finally, you must use an up to date version of python 3 (3.6.4 >=) to run this script

How To Use 
Run the script using the command
python3 BLSScraper.py

new : create a new request
send : send the requests
write : write the responses of the sent requests
exit : exit the program
show : show the current requests from this session
delete : delete a request from the queue
help : more info about the commands







