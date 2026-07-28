from astropy.io import fits
import matplotlib.pyplot as plt

filename = "/Users/gayathrykj/Downloads/CEERS/stage2_cal/jw01345062001_03201_00002_nrcalong_cal.fits"

hdul = fits.open(filename)

# Show the FITS structure
hdul.info()

# Read the calibrated science image
image = hdul["SCI"].data

print("Shape:", image.shape)

# Display the image
plt.figure(figsize=(8, 8))
plt.imshow(image, origin="lower", cmap="gray")
plt.colorbar(label="MJy/sr")
plt.title("JWST CEERS Stage 2 Calibrated Image")
plt.show()

hdul.close()