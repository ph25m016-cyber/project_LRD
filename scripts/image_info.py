from astropy.utils.data import download_file
from astropy.io import fits

# Download FITS file
image_file = download_file(
    "http://data.astropy.org/tutorials/FITS-images/HorseHead.fits",
    cache=True
)

# Open FITS
hdul = fits.open(image_file)

# Read image
image = hdul[0].data

print("Shape :", image.shape)
print("Type :", image.dtype)
print("Minimum :", image.min())
print("Maximum :", image.max())
print("Mean :", image.mean())

hdul.close()
