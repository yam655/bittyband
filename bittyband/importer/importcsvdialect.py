
import csv
import curses.ascii

class ImportCsvDialect(csv.Dialect):
    lineterminator = "\n"
    quoting = csv.QUOTE_NONNUMERIC
    delimiter = "\t"
    doublequote = True
    escapechar = None
    quotechar = '"'
