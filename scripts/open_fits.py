from astropy.io import fits

filename = "/Users/gayathrykj/Downloads/CEERS/raw_uncal/jw01345062001_03201_00002_nrcb1_uncal.fits"

hdul = fits.open(filename)

image = hdul[1].data

print(image.shape)
import matplotlib.pyplot as plt

plt.imshow(image[0,0,:,:], origin="lower", cmap="gray")
plt.colorbar()
plt.show()