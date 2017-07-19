import csv
import logging
import sys

from ProgressBar import ProgressBar
from FindApartment import find_apartment
from GetParcelURI import get_parcel_uri


def init_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # init the console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # init the DEBUG (and up/more severe) logfile handler
    dfh = logging.FileHandler('logfile.log')
    dfh.setLevel(logging.INFO)
    dfh.setFormatter(formatter)
    root.addHandler(dfh)

    # init the ERROR logfile handler
    efh = logging.FileHandler('error.log')
    efh.setLevel(logging.ERROR)
    efh.setFormatter(formatter)
    root.addHandler(efh)

init_logging()

graph_name = 'http://data.labs.pdok.nl/linksets/id/bag-brk'
pand_base_uri = 'http://bag.basisregistraties.overheid.nl/bag/id/pand/'
link_predicate = 'http://data.labs.pdok.nl/linksets/def/bag_brk#relatedParcel'


# init the array of already processed items
processed_lines = []

try:
    with open('processed-lines.csv', 'r') as pr:
        processed = csv.reader(pr)
        for line in processed:
            processed_lines.append(line)
except Exception as e:
    logging.warning(e)


def is_already_processed(cadastral_designation):
    for item in processed_lines:
        if item[0] == cadastral_designation:
            return True
    return False


def run(file_path):
    row_counter = 0
    linkset = open('linkset.nq', 'a')

    processed_writer = csv.writer(open('processed-lines.csv', 'a', newline=''), quoting=csv.QUOTE_NONNUMERIC)

    with open(file_path) as lko:
        lko_reader = csv.reader(lko)

        with open(file_path) as count_lines:
            number_of_rows = sum(1 for _ in csv.reader(count_lines))

        for row in lko_reader:
            row_counter += 1
            ProgressBar.update_progress(row_counter / number_of_rows)

            if not row[0]:
                continue  # There could be empty rows at the end of the data source

            # If the URI has already been processed: skip
            if is_already_processed(row[0]):
                logging.debug('Skipping already matched or failed designation %s' % row[0])
                continue

            # Parse particulars from cadastral designation
            cadastral_designation = row[0]
            pand_id = row[1]
            match_type = row[2]

            parameters = {
                'kadastraleGemeentecode': cadastral_designation[0:5],  # cadastral municipality name
                'sectie': cadastral_designation[5:7].strip(),  # cadastral municipality section
                'perceelnummer': int(cadastral_designation[7:12])  # parcel number
            }

            # If labeled with an 'A' for 'apartment' rather than 'G':
            if cadastral_designation[12] == 'A':
                logging.debug('Apartment right %s' % cadastral_designation)
                apartment_designation = cadastral_designation[0:13] + '0000'
                parcel_matches = find_apartment(apartment_designation)

                if len(parcel_matches) == 0:
                    logging.error('Unable to find corresponding mother parcel for apartment %s' % apartment_designation)
                    parcel_error = 'Geen moederperceel gevonden'
                    processed_writer.writerow(
                        [cadastral_designation, pand_id, match_type, None, None, None, parcel_error])
                    continue
                elif len(parcel_matches) == 1:
                    # Override parcel parameter for the API lookup to the 'mother parcel'
                    parameters['perceelnummer'] = int(parcel_matches[0][7:12])
                else:
                    # TODO: add multiple apartment mother parcel matches
                    logging.debug('Multiple mother parcels for apartment %s' % apartment_designation)

                    for match in parcel_matches:
                        # Override parcel parameter for the API lookup to the 'mother parcel'
                        parameters['perceelnummer'] = int(match[7:12])

                        try:
                            parcel_uri = get_parcel_uri(parameters)
                        except ValueError as parcel_error:
                            logging.error(parcel_error)
                            processed_writer.writerow(
                                [cadastral_designation, pand_id, match_type, parcel_uri, '', match, str(parcel_error)])
                            continue

                        # If successful, save the uri and mother parcel for reference
                        processed_writer.writerow(
                            [cadastral_designation, pand_id, match_type, parcel_uri, '', match, None])
                        linkset.write('<%s> <%s> <%s> <%s>. \n' % (
                            pand_base_uri + pand_id, link_predicate, parcel_uri, graph_name))

            try:
                parcel_uri = get_parcel_uri(parameters)
            except ValueError as parcel_error:
                logging.error(parcel_error)
                processed_writer.writerow(
                    [cadastral_designation, pand_id, match_type, parcel_uri, '', '', str(parcel_error)])
                continue

            processed_writer.writerow([cadastral_designation, pand_id, match_type, parcel_uri, '', '', None])
            linkset.write('<%s> <%s> <%s> <%s>. \n' % (pand_base_uri + pand_id, link_predicate, parcel_uri, graph_name))

    logging.info('Finished!')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please supply the file path to process, exiting')
    else:
        file_path = sys.argv[1]
        run(file_path)
