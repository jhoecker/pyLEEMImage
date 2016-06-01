#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function
import struct
import numpy as np
import sys
import logging
from datetime import datetime, timedelta
########## TODOS ##########
# Fix FOV for python2
########## FIXMES #########


class LEEMImg:
    """Full data of Elmitec LEEM files (image + metadata) but without overlay
    data. Tested with U-View 2002 11.3.0 and LEEM III in Bremen and extended
    for data fields from LEEM/XPEEM at I311 at MaxLAB III.
    No support for dav-files!"""

    def __init__(self, *args):

        if len(args) > 0:
            self.filename = args[0]
            self.metadata = {}
            logging.info('---------------------------------------------------')
            logging.info('FILE:\t{}'.format(self.filename))
            logging.info('---------------------------------------------------')
            self._load_file()
            logging.info('---------------------------------------------------')

    def _load_file(self):
        """Read metadata and image data from file."""

        def convert_ad_timestamp(timestamp):
            """Convert time stamp in windows time format to datetime object."""
            epoch_start = datetime(year=1601, month=1, day=1)
            seconds_since_epoch = timestamp/10**7
            return epoch_start + timedelta(seconds=seconds_since_epoch)

        def read_field(header, iterable, current_position):
            """Read data fields formatted
            name(str)-unit(ASCII digit)-0-value(float)."""
            units_dict = ('', 'V', 'mA', 'A', '°C', ' K', 'mV', 'pA', 'nA', '\xb5A')
            temp = header[current_position+1:].split(b'\x00')[0]
            name = temp[:-1].decode('cp1252')
            if sys.version_info[0] > 2:
                unit_tag = int(chr(temp[-1]))
            else:
                unit_tag = int(temp[-1])
            val = struct.unpack('<f', header[position + len(temp)
                                + 2:position + len(temp) + 6])[0]
            offset = len(temp) + 5  # length of entire field
            return name, units_dict[unit_tag], val, offset

        def read_varian(header, iterable, current_position):
            """Read data fields for varian pressure gauges."""
            temp_1 = header[current_position+1:].split(b'\x00')[0]
            temp_2 = header[current_position+1:].split(b'\x00')[1]
            str_1 = temp_1.decode('cp1252')  # Name
            str_2 = temp_2.decode('cp1252')  # Unit
            val = struct.unpack('<f', header[position+len(temp_1)+len(temp_2)
                                + 3:position+len(temp_1)+len(temp_2)+7])[0]
            offset = len(temp_1)+len(temp_2)+6  # length of entire field
            logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(header[current_position],
                         str_1+':', val, str_2))
            return str_1, str_2, val, offset

        # open file and read header contents
        with open(self.filename, 'rb') as f:

            self.metadata['id'] = f.read(20).split(b'\x00')[0]
            self.metadata['size'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['version'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['bitsperpix'] = struct.unpack('<h', f.read(2))[0]

            f.seek(6,1)  # for alignment
            f.seek(8,1)  # spare

            self.metadata['width'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['height'] = struct.unpack('<h', f.read(2))[0]
            logging.info('\tDimensions:\t {} x {}'.format(
                self.metadata['width'], self.metadata['height']))
            self.noimg = struct.unpack('<h', f.read(2))[0]
            attachedRecipeSize = struct.unpack('<h', f.read(2))[0]

            f.seek(56,1)  # spare

            # read recipe if there is one
            if attachedRecipeSize:
                self.metadata['recipe'] = f.read(attachedRecipeSize)
                f.seek(128-attachedRecipeSize, 1)

            # read first block of image header
            self.metadata['isize'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['iversion'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['colorscale_low'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['colorscale_high'] = struct.unpack('<h', f.read(2))[0]

            self.metadata['timestamp'] = convert_ad_timestamp(struct.unpack('<Q', f.read(8))[0])
            logging.info('\tTime Stamp:\t{}'.format(
                  self.metadata['timestamp'].strftime("%Y-%m-%d %H:%M")))
            self.metadata['mask_xshift'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['mask_yshift'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['usemask'] = f.read(1)

            f.seek(1,1)  # spare

            self.metadata['att_markupsize'] = struct.unpack('<h', f.read(2))[0]
            self.metadata['spin'] = struct.unpack('<h', f.read(2))[0]
            self.versleemdata = struct.unpack('<h', f.read(2))[0]

            logging.info('\tCOLLECTING META DATA:\t')
            # read second block of image header into byte sequence
            #      -     usually block of 256 bytes
            #     -     if too many metadata are stored, 388 empty bytes
            #        followed by number given in versleemdata
            if self.versleemdata == 2:
                img_header = f.read(256)
            else:
                f.seek(388,1)
                img_header = f.read(self.versleemdata)
            position = 0
            #### DEBUG ####
            logging.debug('type(img_header) = {}'.format(type(img_header)))
            ###############
            b_iter = iter(img_header)
            # data_fields with standard format in Bremen
            known_tags = [11,38,39,44,158,159,160,161,162,163,164,165,149,175,
                          184,169,128,129,130,131,132,133,134,135,136,137,138,
                          140,141,142,143,144,145,146,147,148,150,151,152,153,
                          154,155,168,170,171,173,174]
            # additional fields knwon for LUND
            known_tags.extend([210,203,185,208,215,206,172,211,221,220,197,177,
                               178,180,181,202,190,191,194,195,196,214,198,199,
                               182,179,200,201,176,187,94,192,213,209,183,186,
                               212,156,157,205,204,188,189,207])
            # for ALBA: Wehnelt tag 55
            known_tags.extend([55])

            # use iterator to search img_header byte-wise for data field tags
            for b in b_iter:
                if sys.version_info[0] < 3:
                    b = ord(b)
                #### DEBUG ####
                logging.debug('b = {}'.format(b))
                ###############
                # stop when reaching end of header
                if b == 255:
                    break
                # Data fields with standard format
                elif b in known_tags:
                    [fieldname, unit, value, offset] = read_field(img_header, b_iter, position)
                    self.metadata[fieldname] = [value, unit]
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        b, fieldname+':', value, unit))
                # FOV
                elif b == 110:
                    temp = img_header[position+1:].split(b'\x00')[0]
                    fov_str = temp.decode('cp1252')
                    self.metadata['FOV cal. factor'] = \
                        float(struct.unpack('<f', img_header[position+len(temp)+2:position+len(temp)+6])[0])
                    # for LEED images
                    if fov_str[0:4] == 'LEED':
                        self.metadata['LEED'] = True
                        self.metadata['FOV'] = None
                        logging.info('\t{:>3}\t{:<18}\t{}'.format(
                            b, 'Field Of View:', 'LEED'))
                        logging.info('\t{:>3}\t{:<18}\t{}'.format(
                            '', 'FOV cal. factor:', self.metadata['FOV cal. factor']))
                    # for normal images
                    else:
                        ##### DEBUG #####
                        logging.debug('fov_str = {}'.format(temp))
                        #################
                        ## TODO FIX FOV for python2
                        if sys.version_info[0] > 2:
                            self.metadata['LEED'] = False
                            self.metadata['FOV'] = \
                                [float(fov_str.split('\xb5m')[0]), '\xb5m']
                            logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                                b, 'Field Of View:',
                                self.metadata['FOV'][0],
                                self.metadata['FOV'][1]))
                            logging.info('\t{:>3}\t{:<18}\t{}'.format(
                                '', 'FOV cal. factor:',
                                self.metadata['FOV cal. factor']))
                        else:
                            logging.warning('Read FOV not implemented for python < v3!')
                            self.metadata['FOV'] = 'LEEM'

                    offset = len(temp)+5
                # Camera Exposure
                elif b == 104:
                    self.metadata['Camera Exposure'] = [struct.unpack('<f', img_header[position+1:position+5])[0], 's']
                    self.metadata['Average Images'] = img_header[position+5]
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        b, 'Camera Exposure:',
                        self.metadata['Camera Exposure'][0],
                        self.metadata['Camera Exposure'][1]))
                    if self.metadata['Average Images'] == 0:
                        logging.info('\t{:>3}\t{:<18}\t{:s} {}'.format(
                            '', 'Average Images:',
                            self.metadata['Average Images'],
                            '\t=> No Averaging'))
                    elif self.metadata['Average Images'] == 255:
                        logging.info('\t{:>3}\t{:<18}\t{:s} {}'.format(
                            '', 'Average Images:',
                            self.metadata['Average Images'],
                            '\t=> Sliding Average'))
                    else:
                        if sys.version_info[0] > 2:
                            logging.info('\t{:>3}\t{:<18}\t{:g}'.format(
                                '', 'Average Images:',
                                self.metadata['Average Images']))
                        else:
                            logging.info('\t{:>3}\t{:<18}\t{:g}'.format(
                                         '', 'Average Images:',
                                         ord(self.metadata['Average Images'])))

                    offset = 6
                # Pressure Gauges
                elif b in [106, 107, 108, 109, 235, 236, 237]:
                    [pressure_gauge, unit, pressure, offset] = \
                        read_varian(img_header, b_iter, position)
                    self.metadata[pressure_gauge] = [pressure, unit]
                # Mitutoyos
                elif b == 100:
                    self.metadata['Mitutoyo X'] = \
                        [struct.unpack('<f', img_header[position+1:position+5])[0], 'mm']
                    self.metadata['Mitutoyo Y'] = \
                        [struct.unpack('<f', img_header[position+5:position+9])[0], 'mm']
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        b, 'Mitutoyo X:', self.metadata['Mitutoyo X'][0],
                        self.metadata['Mitutoyo X'][1]))
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        '', 'Mitutoyo Y:', self.metadata['Mitutoyo Y'][0],
                        self.metadata['Mitutoyo X'][1]))
                    offset = 8

                # Image Title. WARNING: Not sure! Probably null-terminated string.
                elif b == 233:
                    temp = img_header[position+1:].split(b'\x00')[0]
                    self.metadata['Image Title'] = temp.decode('cp1252')
                    logging.info('\t{:>3}\t{:<18}\t{}'.format(
                        b, 'Image Title:', self.metadata['Image Title']))
                    offset = len(temp) + 1

                # WARNING: Correct usage of 242, 243, 244 is unclear!
                #          242 (MirrorState) format guess: single byte, null
                #          243    (MCPScreen)    probably float for screen voltage
                #          244 (MCPchanneplate) probably float for channelplate voltage
                elif b == 242:
                    self.metadata['MirrorState'] = img_header[position+1]
                    logging.info('\t{:>3}\t{:<18}\t{:g}'.format(b, 'MirrorState:', self.metadata['MirrorState']))
                    offset = 2

                elif b == 243:
                    self.metadata['MCPscreen'] = [struct.unpack('<f', img_header[position+1:position+5])[0], 'V']
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        b, 'MCPscreen:', self.metadata['MCPscreen'][0], self.metadata['MCPscreen'][1]))
                    offset = 4

                elif b == 244:
                    self.metadata['MCPchannelplate'] = [struct.unpack('<f', img_header[position+1:position+5])[0], 'V']
                    logging.info('\t{:>3}\t{:<18}\t{:g} {}'.format(
                        b, 'MCPchannelplate:', self.metadata['MCPchannelplate'][0],
                        self.metadata['MCPchannelplate'][1]))
                    offset = 4

                # Just in case I forgot something:
                else:
                    logging.warning('WARNING: Unknown field tag {0} at\
                            position {1}. This and following data fields might\
                            be misinterpreted!'.format(b, position))

                # skip byte number given by offset - depending on length of
                # read data field, update position counter
                [next(b_iter) for x in range(offset)]
                position += offset + 1

            # Now read image data
            f.seek(-2*self.metadata['height']*self.metadata['width'], 2)
            self.data = np.fromfile(f, dtype=np.uint16, sep='')
            self.data = self.data.reshape(
                [self.metadata['height'], self.metadata['width']])


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    # for test purposes
    im = LEEMImg('testfiles/CCD_2x2.dat')

    #import matplotlib.pyplot as plt
    #fig = plt.figure(frameon=False, figsize=(3, 3*im.height/im.width), dpi=im.width/3)
    #ax = plt.Axes(fig, [0., 0., 1., 1.])
    #ax.set_axis_off()
    #fig.add_axes(ax)
    #ax.imshow(im.data, cmap='gray', clim=(np.amin(im.data), np.amax(im.data)), aspect='normal')
    #plt.show()
