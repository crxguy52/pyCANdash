import logging
import sys
import can
import cantools
import csv
import math
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, show
from bokeh.palettes import Category10


def handleException():
    # Handle errors raised by the script and log them
    exc_type, exc_value, exc_traceback = sys.exc_info()
    # Ignore keyboard interrupts so a console program can exit with ctrl + c
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.error("Uncaught exception: ", exc_info=(exc_type, exc_value, exc_traceback))

def colorName2hex(colorName):
    color2hex = {
        'white': '#ffffff',
        'darkgray': '#808080',
        'gray': '#a0a0a4',
        'lightgray': '#c0c0c0',
        'red': '#ff0000', 
        'green': '#00ff00', 
        'blue': '#0000ff',
        'cyan': '#00ffff',
        'magenta': '#ff00ff', 
        'yellow': '#ffff00', 
        'darkred': '#800000', 
        'darkgreen': '#008000', 
        'darkblue': '#000080', 
        'darkcyan': '#008080', 
        'darkmagenta': '#800080', 
        'darkyellow': '#808000', 
        'transparent': '#00000000',
    }
    if colorName.lower() in color2hex.keys():
        color = color2hex[colorName.lower()]
    else:
        color = colorName
        logging.info(f'Color {colorName} not found')
    
    return color


def findUnit(sigName, canChans, useIps=None):
    # Find the units
    unit = ''

    for chan in canChans:
        if sigName in canChans[chan]['sig2unit']:
            if canChans[chan]['sig2unit'][sigName] is not None:
                unit = canChans[chan]['sig2unit'][sigName] 
                unit = unit.replace('deg', '°')

    if useIps is not None:
        if useIps:
            return convert2ips(unit)
        else:
            return unit, 1, 0
    else:
        return unit
        

def convert2ips(unit:str):
    conversions = {
        # newVal = oldVal*gain + offset
        'kpa':{'gain':0.145038, 'offset':0, 'newUnit':'psi'},
        'kph':{'gain':0.621371, 'offset':0, 'newUnit':'mph'},
        '°c':{'gain':9/5, 'offset':32, 'newUnit':'°F'},
        'rpm':{'gain':1e-3, 'offset':0, 'newUnit':'kRPM'},
    }

    if unit.lower() in conversions:
        newUnit = conversions[unit.lower()]['newUnit']
        gain = conversions[unit.lower()]['gain']
        offset = conversions[unit.lower()]['offset']

    else:
        gain = 1
        offset = 0
        newUnit = unit
        logging.warning(f'Unable to convert {unit} to ips')

    return newUnit, gain, offset 


def decode_tall(fPath, dbPath):
    db = cantools.database.load_file(dbPath)
    noDecode = []

    # Write it to a tall format
    tallfn = f'{fPath[:-4]}_tall.csv'
    print(f'Decoding {tallfn}')
    with open(tallfn, 'w') as f:

        # Write the header
        f.write('timestamp,signal,value\n')

        # Iterate over all the messages
        for msg in can.LogReader(fPath):

            if msg.arbitration_id not in noDecode:
                try:
                    message = db.get_message_by_frame_id(msg.arbitration_id)
                    signals = message.decode(msg.data)
                    for signal in signals:

                        # Write it to the tall file
                        f.write(f"{msg.timestamp},{signal},{signals[signal]}\n")

                except:
                    # Skip it next time if there was an error decoding
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    print(f'Error decoding {msg.arbitration_id}: {exc_type}, skipping')
                    noDecode.append(msg.arbitration_id)


def decode_wide(
    tall_file_name: str,
    wide_file_name: str,
    timestamp_col: str = "timestamp_received",
    sample_time_ms: int = 10,
    fill_na: bool = False,
) -> None:
    """Pivot a tall file to wide format.

    Rows of the wide file will be spaces sample_time_ms apart, and each row will have the latest value for each signal
    up to that timestamp.

    Args:
        tall_file_name: name of existing tall file to pivot to wide
        wide_file_name: name of the wide file to write
        timestamp_col: column name of the timestamp to use for pivoting
        sample_time_ms: sample time of each row in milliseconds
    """
    isoformat = False  # how to write timestamp out
    values: dict[str, Any] = {"timestamp": None}  # want timestamp to always be first
    increment = sample_time_ms / Decimal(1000)

    # first get all column names
    # see https://docs.python.org/3/library/csv.html#id1 for explanation of newline=''
    with open(tall_file_name, "r", newline="") as file_in:
        reader = csv.reader(file_in)
        # read headers into map name -> index
        header_mapping = {value: index for index, value in enumerate(next(reader))}
        field_index = header_mapping["signal"]
        value_index = header_mapping["value"]

        # get unique set of field names
        fields = set(row[field_index] for row in reader)

    # update dictionary with sorted list of columns (remember timestamp is already there)
    values.update({field: None for field in sorted(fields)})

    # now loop again, actually writing pivoted CSV
    # see https://docs.python.org/3/library/csv.html#id1 for explanation of newline=''
    with open(wide_file_name, "w", newline="") as file_out:
        writer = csv.writer(file_out, lineterminator=os.linesep)  # use system new line even
        # write header
        writer.writerow(values.keys())

        def write_row() -> None:
            writer.writerow(value if value is not None else "" for value in values.values())

        with open(tall_file_name, "r", newline="") as file_in:
            next(file_in)  # skip header
            reader = csv.reader(file_in)
            row_timestamp = None
            for row in reader:
                timestamp_value = row[header_mapping[timestamp_col]]
                # robust to isoformat timestamps as well
                try:
                    timestamp = Decimal(timestamp_value)
                except InvalidOperation:
                    timestamp = Decimal(datetime.fromisoformat(timestamp_value).timestamp())
                    isoformat = True

                if row_timestamp is None:
                    # determine the first row timestamp as the next round sample_time ms increment
                    row_timestamp = Decimal(math.ceil((timestamp * 1000) / sample_time_ms) * sample_time_ms) / 1000
                elif timestamp > row_timestamp:
                    # since each row will have the latest value up to that timestamp, as soon as we go past that
                    # timestamp we are done with that row, so write the row, and increment timestamp
                    values["timestamp"] = (
                        row_timestamp if not isoformat else datetime.fromtimestamp(float(row_timestamp)).isoformat()
                    )
                    write_row()
                    if not fill_na:
                        values.update({field: None for field in sorted(fields)})
                    while row_timestamp <= timestamp:
                        # find next timestamp increment greater than current timestamp
                        row_timestamp += increment
                values[row[field_index]] = row[value_index]

            # write the last row -- there will always be at least one more value received since last write
            if row_timestamp is not None:
                values["timestamp"] = (
                    row_timestamp if not isoformat else datetime.fromtimestamp(float(row_timestamp)).isoformat()
                )

            write_row()


def tryConvert2float(val :str):
    try:
        floatVal = float(val)
        val = floatVal
    except:
        pass

    return val


if __name__ == "__main__":
    gfpath = 'Z:/My Drive/fastboi/guiv2/data/'
    gfn = '20241117_130733.blf'

    decode_tall(gfpath + gfn, 'Z:/My Drive/fastboi/guiv2/dbc/gmlan_v1.4.dbc')
    print('Finished decoding tall')

    print('Decoding wide')
    decode_wide(gfpath + gfn[:-4]+'_tall.csv', gfpath + gfn[:-4]+'_wide.csv', timestamp_col='timestamp', fill_na=True)
    print('Done decoding')

    print('Deleting tall')
    os.remove(gfpath + gfn[:-4]+'_tall.csv')
    print('done')

    #print('Converting wide to dict')
    #out = {}
    #with open(fpath+fn[:-4]+'_wide.csv') as csvfile:
    #    reader = csv.DictReader(csvfile)
    #    for row in reader:
    #        for column, value in row.items():
    #            if column not in out:
    #                out.update({column:[tryConvert2float(value)]})
    #            else:
    #                out[column].append(tryConvert2float(value))

    #out['timestamp'] = [t - out['timestamp'][0] for t in out['timestamp']]

    #print('Converting dict to columndatasource')
    #source = ColumnDataSource(out)

    #print('creating figure')
    ## create a first plot with all data in the ColumnDataSource
    #p = figure(height=800, width=800, sizing_mode="stretch_both")

    #plotVars = ['accelerator_actual_pos', 'throttle_pos']
    ##plotVars = ['ambient_air_temp', 'engine_coolant_temp', 'engine_intake_air_temp', 'engine_oil_temperature', 'trans_oil_temp']
    #colors = Category10[max([3, len(plotVars)])]
    #for idx in range(0, len(plotVars)): 
    #    p.line(source=source, x='timestamp', y=plotVars[idx], legend_label=plotVars[idx], color=colors[idx])

    ## show both plots next to each other in a gridplot layout
    #show(p)