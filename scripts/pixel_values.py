from astropy.utils.data import download_file
from astropy.io import fits

image_file = download_file(
    "http://data.astropy.org/tutorials/FITS-images/HorseHead.fits",
    cache=True
)

hdul = fits.open(image_file)

image = hdul[0].data

# print(image[0,0])
# print(image[100,100])
# print(image[446,447])
print("Brightest pixel =", image.max())
import numpy as np

brightest = np.argmax(image)

print(brightest)
row, col = np.unravel_index(np.argmax(image), image.shape)

print("Row =", row)
print("Column =", col)
print("Brightness =", image[row, col])


hdul.close()