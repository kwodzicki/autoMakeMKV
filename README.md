# AutoMakeMKV

This python package is designed to take the guess work out of media backup.
Comprised of this package and a separate database of disc information, automatic backup and tagging of files is possible.
Simply start the software, point it to the database, and start inserting discs.
If a disc is NOT found in the database, a GUI will appear on screen enabling you to tag the tracks to be backed up from the disc.
After this informaiton is entered, the backup will begin.

# The Database

A separate git repo houses the disc database.
This database consists of JSON files with information about which track(s) to backup from the disc and output from the MakeMKV program.
The files are named using the UUID of the disc as determined from UDEV on Linux operating systems.

To get the database, go to (insert link to database git repo here) and follow the instructions for cloning the repo.
As you begin backing up discs, you will likely encounter discs that are not in the database.
Please create commits/merge requests as new discs are added to improve the experience for other users; if enough people do this, it will become very easy for the community to backup discs.
Also, don't forget to do a periodic pull from the database to ensure you have the most up-to-date listing of discs.

For more information about the database, refer to the database README.

# The GUI


