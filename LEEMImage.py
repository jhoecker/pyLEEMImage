#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python LEEM image module
(c) 2016 Jon-Olaf Krisponeit, Jan Höcker

License: LGPL
"""

import struct
import numpy as np
import scipy.ndimage
import sys
import logging
from datetime import datetime, timedelta

class LEEMImage:
    """Import full data of Elmitec LEEM files (image + metadata) but without overlay
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
            #logging.debug('type(img_header) = {}'.format(type(img_header)))
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
                #logging.#debug('b = {}'.format(b))
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
                    # for normal images
                    elif fov_str[0:4] == 'none':
                        self.metadata['FOV'] = None
                        logging.info('\t{:>3}\t{:<18}\t{}'.format(
                            b, 'Field Of View:', 'None'))
                    else:
                        self.metadata['LEED'] = False
                        try:
                            self.metadata['FOV'] = [float(fov_str.split('\xb5m')[0]), '\xb5m']
                            logging.info('\t{:>3}\t{:<18}\t{} {}'.format(
                                b, 'Field Of View:',
                                self.metadata['FOV'][0],
                                self.metadata['FOV'][1]))
                        except ValueError:
                            logging.error('FOV field tag: not known string detected: {}'.format(fov_str))
                    logging.info('\t{:>3}\t{:<18}\t{}'.format('',
                                                              'FOV cal. factor:',
                                                              self.metadata['FOV cal. factor']))
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
                        logging.info('\t{:>3}\t{:<18}\t{:d} {}'.format(
                            '', 'Average Images:',
                            self.metadata['Average Images'],
                            '\t=> No Averaging'))
                    elif self.metadata['Average Images'] == 255:
                        logging.info('\t{:>3}\t{:<18}\t{:d} {}'.format(
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

                # WARNING: Correct usage of 240, 242, 243, 244 is unclear!
                #          240 (MirrorState1) format guess: single byte, null
                #          242 (MirrorState2) format guess: single byte, null
                #          243   (MCPScreen)    probably float for screen voltage
                #          244 (MCPchanneplate) probably float for channelplate voltage
                elif b == 240:
                    self.metadata['MirrorState1'] = img_header[position+1]
                    logging.info('\t{:>3}\t{:<18}\t{:g}'.format(b, 'MirrorState1:', self.metadata['MirrorState1']))
                    offset = 2

                elif b == 242:
                    self.metadata['MirrorState2'] = img_header[position+1]
                    logging.info('\t{:>3}\t{:<18}\t{:g}'.format(b, 'MirrorState2:', self.metadata['MirrorState2']))
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
                    logging.error('ERROR: Unknown field tag {0} at '\
                            'position {1}. This and following data fields might '\
                            'be misinterpreted!'.format(b, position))

                # skip byte number given by offset - depending on length of
                # read data field, update position counter
                [next(b_iter) for x in range(offset)]
                position += offset + 1

            # Now read image data
            f.seek(-2*self.metadata['height']*self.metadata['width'], 2)
            self.data = np.fromfile(f, dtype=np.uint16, sep='')
            self.data = self.data.reshape(
                [self.metadata['height'], self.metadata['width']])
            # Flip image to get the original orientation
            self.data = np.flipud(self.data)

    def normalizeOnCCD(self, lCCD):
        """Normalize LEEM image on CCD"""
        if type(lCCD) is not LEEMImage:
            raise TypeError('Image divisor not of type UKSoft')
        if (self.metadata['width']!= lCCD.metadata['width'] or
            self.metadata['height'] != lCCD.metadata['height']):
            raise DimensionError('Dimensions of LEEM image and CCD image do not match')
        correctedData = np.divide(self.data,lCCD.data)
        correctedData /= correctedData.max()
        return correctedData

    def filterInelasticBkg(self, sigma=15):
        """Experimental function to remove the inelastic background in
        LEED images. Works like a high-pass filter by subtracting the
        gaussian filtered image."""
        self.data = np.divide(self.data, self.data.max())
        dataGaussFiltered = scipy.ndimage.gaussian_filter(self.data, sigma)
        return self.data - dataGaussFiltered

    def get_levels(self, data=None):
        """Calculates good min/max values to obtain a good contrast.
        Differentiate LEEM and LEED mode: For LEEM images only consider
        the inner square (cutting off the edges usually appearing dark due to the
        round MCP). For LEED consider the full image because the intensity
        of the diffuse background is usually as low as the darkcounts.
        Argument might be used if image data is corrected, which is not stored
        as LEEMImage instance"""

        def inner_square_size(length):
            """ Determine size of inner square of a circle"""
            offset = 5
            return int(length/(2*np.sqrt(2)))-5

        data = self.data if data is None else data

        # Consider only the inner square for levels if image is a LEEM image
        try:
            if self.metadata['LEED'] is False:
                nrows, ncols = data.shape[0], data.shape[1]
                new_nrows = inner_square_size(nrows)
                new_ncols = inner_square_size(ncols)
                data = data[int(nrows/2)-new_nrows:int(nrows/2)+new_nrows,
                            int(ncols/2)-new_ncols:int(ncols/2)+new_ncols]
        except KeyError:
            pass

        data_histogram = np.histogram(data, bins=30)
        minlevel = data_histogram[1][0]
        nhotpixel = 10
        # Ignore hotpixels when setting intensity
        if data_histogram[0][-1] < nhotpixel and data_histogram[0][-2] < nhotpixel/2:
            logging.debug('LEEMImage.get_levels: {} hotpixels detected'.format(
                data_histogram[0][-1]))
            # Find reverse index
            rn_maxlevel = np.argmax(np.flipud(data_histogram[0]))
            maxlevel = data_histogram[1][-rn_maxlevel]
        else:
            maxlevel = data_histogram[1][-2]
        return minlevel, maxlevel


class DimensionError(Exception):
    """Exception raised when the dimension of two LEEM images are not
    equivalent."""
    def __init__(self, message):
        self.message = message


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    # for test purposes
    im = LEEMImage('testfiles/UniBremen2016.dat')
    #im.normalizeOnCCD()
    #im.filterInelasticBkg()

    import matplotlib.pyplot as plt
    fig = plt.figure(frameon=False, 
                     figsize=(3, 3*im.metadata['height']/im.metadata['width']),
                     dpi=im.metadata['width']/3)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(im.data, cmap='gray',
              clim=(np.amin(im.data),
                    np.amax(im.data)),
              aspect='auto')
    plt.show()
