## LEEM image module
The LEEMImg python module provides functionality to easily import the UKSoft
image format (used by ELMITEC LEEMs) as well as commenly used operations on the
image.

## Functionality
### Data import
The LEEM image is imported as LEEMImg-Object which stores the image as `data`
attribute (numpy array) as well as the available metadata as `metadata`
attribute (dictonary).

### Operations
- Normalize on CCD
- Filter inelastic scattered electron (useful for LEED images recorded without analyzer)

## Requirements
- Python 3
- [Scipy](https://www.scipy.org)

## Authors
- Jon-Olaf Krisponeit (main author of the import functionality)
- Jan Höcker (improvements and packaging)

## License
LGPL
