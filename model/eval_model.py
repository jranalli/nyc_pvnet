import glob

import csv

from model.dataset_manipulation import reshape_inputs
import os
import shutil
import matplotlib.pyplot as plt
import numpy as np

from keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from keras.callbacks import ModelCheckpoint, CSVLogger
from keras.optimizers import Adam, SGD

import segmentation_models as sm

from utils.fileio import read_file_list, verify_dir, is_dir_empty


def eval_model(test_img_dir, test_mask_dir, test_img_file, test_mask_file, weight_file, result_file, pred_dir,
               plot_dir=None, backbone="resnet34", img_size=(576, 576), batchnorm=False, overwrite=False):
    """
    Perform the evaluation of the model

    Parameters
    ----------
    test_img_dir: str
        Directory with test images to predict. Use None for test_img_file that contains full paths.
    test_mask_dir: str
        Directory with test masks. Use None for test_img_file that contains full paths.
    test_img_file: str
        Full context of file containing list of train images
    test_mask_file: str
        Full context of file containing list of train mask images
    weight_file: str
        Full location of saved weights
    result_file: str
        Full location of file to save results to
    pred_dir: str
        Full location of path to save prediction images
    plot_dir: str
        Full location of path to save plot images
    backbone: str
        Model backbone
    img_size: tuple
        Image size in (xxx, yyy)
    batchnorm: bool (default: False)
        Use batchnorm
    overwrite: bool (default: False)
        Should files be overwritten?
    """

    # test and create directories
    verify_dir(pred_dir)
    if not is_dir_empty(pred_dir):
        if not overwrite:
            print("Prediction directory is not empty, skipping operation...")
            return
        else:
            shutil.rmtree(pred_dir)
            verify_dir(pred_dir)

    if plot_dir is not None:
        verify_dir(plot_dir)
        if not is_dir_empty(plot_dir):
            if not overwrite:
                print("Plot directory is not empty, skipping operation...")
                return
            else:
                shutil.rmtree(plot_dir)
                verify_dir(plot_dir)

    # Get the list of all input/output files
    images = read_file_list(test_img_file, test_img_dir)
    masks = read_file_list(test_mask_file, test_mask_dir)

    # Load and reshape the data
    print("==== Load and Resize Data ====")
    x, y = reshape_inputs(images, masks, img_size)

    # Create the model and define metrics
    print("==== Create Model ====")
    model = sm.Unet(backbone,
                    encoder_weights='imagenet',
                    input_shape=(img_size[0], img_size[1], 3),
                    classes=1,
                    decoder_use_batchnorm=batchnorm)
    print("==== Compile Model ====")
    model.compile(
        optimizer=SGD(),
        loss=sm.losses.bce_jaccard_loss,
        metrics=[sm.metrics.iou_score,
                 sm.metrics.precision,
                 sm.metrics.recall,
                 sm.metrics.f1_score],
    )

    # Load the model meights
    print("==== Load Weights ====")
    model.load_weights(weight_file)

    # Perform the metric evaluation
    print("==== Perform Evaluation ====")
    res = model.evaluate(x, y, batch_size=16, verbose=1)

    # Write to file
    print("==== Save Evaluation ====")
    csv_cols = ["weight file"] + list(model.metrics_names)
    csv_row = [os.path.basename(weight_file)] + list(res)

    print(csv_cols)
    print(csv_row)

    with open(result_file, 'w', newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_cols)
        writer.writerow(csv_row)

    # Perform the prediction (images)
    print("==== Perform Predictions ====")
    pred_imgs = model.predict(x, batch_size=16)
    pred_imgs = reshape_arr(pred_imgs)

    x = reshape_arr(x)
    y = reshape_arr(y)

    # Save plots and images
    print("==== Save Predictions ====")
    figsize = 7
    cols = 4
    alpha = 0.5

    for im_id, imname in enumerate(images):
        img_name = os.path.basename(imname)
        plt.imsave(os.path.join(pred_dir, img_name), pred_imgs[im_id],
                   cmap=plt.cm.gray)

        if plot_dir is not None:
            fig, axes = plt.subplots(1, cols,
                                     figsize=(cols * figsize, figsize))
            axes[0].set_title("original", fontsize=15)
            axes[1].set_title("ground truth", fontsize=15)
            axes[2].set_title("prediction", fontsize=15)
            axes[3].set_title("overlay", fontsize=15)
            axes[0].imshow(x[im_id], cmap=get_cmap(x))
            axes[0].set_axis_off()
            axes[1].imshow(y[im_id], cmap=get_cmap(y))
            axes[1].set_axis_off()

            axes[2].imshow(pred_imgs[im_id], cmap=get_cmap(pred_imgs))
            axes[2].set_axis_off()
            axes[3].imshow(x[im_id], cmap=get_cmap(x))
            axes[3].imshow(mask_to_red(zero_pad_mask(pred_imgs[im_id],
                                                     desired_size=img_size[0])),
                           cmap=get_cmap(pred_imgs),
                           alpha=alpha)
            axes[3].set_axis_off()
            fig.savefig(os.path.join(plot_dir, img_name))
            plt.close(fig)


def zero_pad_mask(mask, desired_size):
    pad = (desired_size - mask.shape[0]) // 2
    padded_mask = np.pad(mask, pad, mode="constant")
    return padded_mask


def reshape_arr(arr):
    if arr.ndim == 3:
        return arr
    elif arr.ndim == 4:
        if arr.shape[3] == 3:
            return arr
        elif arr.shape[3] == 1:
            return arr.reshape(arr.shape[0], arr.shape[1], arr.shape[2])


def get_cmap(arr):
    if arr.ndim == 3:
        return 'gray'
    elif arr.ndim == 4:
        if arr.shape[3] == 3:
            return 'jet'
        elif arr.shape[3] == 1:
            return 'gray'


def mask_to_red(mask):
    """
    Converts binary segmentation mask from white to red color.
    Also adds alpha channel to make black background transparent.
    """
    img_size = mask.shape[0]
    c1 = mask.reshape(img_size, img_size)
    c2 = np.zeros((img_size, img_size))
    c3 = np.zeros((img_size, img_size))
    c4 = mask.reshape(img_size, img_size)
    return np.stack((c1, c2, c3, c4), axis=-1)


if __name__ == '__main__':
    pass
    # this is obsolete. Rewrite?
