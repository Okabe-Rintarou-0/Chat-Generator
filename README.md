## SMFile_Parser
Stepmania File Parser for the [Stepmania Note Generator](https://github.com/cpuguy96/stepmania-note-generator) by cpuguy96

Batch processes all .sm files in current dir of smfile_parser.py and parses for:
- Title
- BPM
- Note Timings (in seconds)
- Note Placements (ex. 0001 = 01)

Then writes data to their respective .txt output files for valid .sm files.

Does not support 3/4th measures.

Only reads the first difficulty listed.

changelog:
- cleaned up code for readability
- added formatting to .ogg files found within the directory
- added example hard_humming sm, txt and ogg files
- fixed a bug where the parser skipped the last measure
- replaced holds with normal note for note placement
- added note placement for each note timing as a binary to decimal function, ignores mines
- fixed a bug where the Step lists were not cleared after each file, resulting in abnormally large and incorrect output files
- converted to a no-input, batch processing method for .sm files found within the directory
- added formatting to output .txt file names
- ignores non-ASCII (ex. Japanese) text in the title
