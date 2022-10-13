from zipfile import ZipFile
import os
from PIL import Image
import numpy as np

from utils.fileio import verify_dir


def to_png(source_zip, rgb_dir, ir_dir=None, imgtype="png"):
    """
    Process ZIP files from New York City GIS data download
         (https://gis.ny.gov/gateway/mg/2018/new_york_city/)

    Convert 4 channel JPEG2000 images into 3 channel RGB images and separate
    single channel images of the Infrared channel.

    Parameters
    ----------
    source_zip: str
        full path to the zip file downloaded from the database
    rgb_dir: str
        full path output directory for the rgb images
    ir_dir: str or None (default None)
        full path output directory for the alpha images. If None, alpha images
        are not saved.
    imgtype: str (default "png")
        Extension of the image file name to save as. Must be supported by PIL.
    """

    # Open the zip file for internal access
    with ZipFile(source_zip, "r") as zipdat:

        # Get a list of all files within the zip
        fns = zipdat.namelist()

        # loop over each file within the zip
        for fn in fns:

            # Separate the file name and its extension for this file
            fn_short, ext = os.path.splitext(fn)

            # Check to see if it's an image
            if ext == ".jp2":

                # Just output a status indicator
                print(fn)

                # Make sure our output directories exist
                verify_dir(rgb_dir)
                if ir_dir is not None:
                    verify_dir(ir_dir)

                # Get access to this individual picture file within the zip
                with zipdat.open(fn) as file:

                    # Read it in as a PIL object
                    pic = Image.open(file)

                    # Images have 4 layers (RGB + Infrared).
                    # Convert to NumPy Array for manipulation
                    x, y = pic.size
                    a = np.array(pic.getdata()).reshape(x, y, 4)

                    # Separate RGB and Infrared channels and save each into
                    # a PNG file
                    # Layers 0-2 are RGB
                    im = Image.fromarray(a[:, :, :-1].astype('uint8'))
                    im.save(os.path.join(rgb_dir, fn_short + "." + imgtype))

                    # Layer 3 is Infrared
                    if ir_dir is not None:
                        alpha = Image.fromarray(a[:, :, -1].astype('uint8'))
                        alpha.save(os.path.join(ir_dir, fn_short +
                                                "." + imgtype))


# Example dirs for testing
sourcefile = "c:\\nycdata\\boro_queens_sp18.zip"
outdir = "c:\\nycdata\\boro_queens_sp18_png"
outdir_a = "c:\\nycdata\\boro_queens_sp18_alpha"

if __name__ == "__main__":
    to_png(sourcefile, outdir, outdir_a)
