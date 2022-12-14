import glob, os
# import argparse
#
# import tensorflow as tf
# gpu_options = tf.compat.v1.GPUOptions(allow_growth=True)
# session = tf.compat.v1.InteractiveSession(config=tf.compat.v1.ConfigProto(gpu_options=gpu_options))
from keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from keras.callbacks import ModelCheckpoint, CSVLogger, EarlyStopping
from keras.optimizers import Adam, SGD


import segmentation_models as sm


# from livelossplot import PlotLossesKeras


from model.dataset_manipulation import reshape_inputs
from utils.fileio import read_file_list, verify_dir


def write_header(csvfile, train_img_dir, train_mask_dir,
               train_img_file, train_mask_file, valid_img_file, valid_mask_file,
               best_weight_file, end_weight_file, valid_img_dir, valid_mask_dir,
               backbone, seed, img_size,
               epochs, freeze_encoder, patience, batchnorm, augment_dict):

    verify_dir(os.path.dirname(csvfile))

    with open(csvfile, "w") as f:
        for name in ['train_img_dir', 'train_mask_dir', 'train_img_file', 'train_mask_file', 'valid_img_file', 'valid_mask_file',
               'best_weight_file', 'end_weight_file', 'valid_img_dir', 'valid_mask_dir', 'backbone', 'seed', 'img_size', 'epochs', 'freeze_encoder', 'patience', 'batchnorm']:
            f.write(name+",")
        f.write("\n")
        for val in [train_img_dir, train_mask_dir,
               train_img_file, train_mask_file, valid_img_file, valid_mask_file,
               best_weight_file, end_weight_file, valid_img_dir, valid_mask_dir,
               backbone, seed, img_size,
               epochs, freeze_encoder, patience, batchnorm]:
            f.write(str(val).replace(",", ";") + ",")
        f.write("\n")
        for key in augment_dict.keys():
            f.write(key + ",")
        f.write("\n")
        for key in augment_dict.keys():
            f.write(str(augment_dict[key]).replace(",", ";") + ",")
        f.write("\n\n")
        f.write("epoch,train_loss,train_IOU,val_loss,val_IOU\n")


def get_augmented(
        X_train,
        Y_train,
        batch_size=32,
        seed=0,
        data_gen_args=dict(
            rotation_range=10.0,
            height_shift_range=0.02,
            shear_range=5,
            horizontal_flip=True,
            vertical_flip=False,
            fill_mode="constant",
        )
    ):
    """
    Copied from keras_unet: https://github.com/karolzak/keras-unet
    Duplicated here just to reduce dependencies

    Note that because get_augmented is only used for the training data, this
    may be one cause of validation loss being lower than training loss.

    Parameters
    ----------
    X_train
    Y_train
    batch_size
    seed
    data_gen_args

    Returns
    -------

    """
    # Train data, provide the same seed and keyword arguments to the fit and
    # flow methods
    X_datagen = ImageDataGenerator(**data_gen_args)
    Y_datagen = ImageDataGenerator(**data_gen_args)
    X_datagen.fit(X_train, augment=True, seed=seed)
    Y_datagen.fit(Y_train, augment=True, seed=seed)
    X_train_augmented = X_datagen.flow(
        X_train, batch_size=batch_size, shuffle=True, seed=seed
    )
    Y_train_augmented = Y_datagen.flow(
        Y_train, batch_size=batch_size, shuffle=True, seed=seed
    )

    train_generator = zip(X_train_augmented, Y_train_augmented)
    return train_generator


# Questions:
#   - Should we try tuning the learning rate:
#       https://pyimagesearch.com/2019/08/05/keras-learning-rate-finder/
#   - Should we use Freeze_encoder? Batchnorm? Monte Carlo Dropout?


def train_unet(train_img_dir, train_mask_dir,
               train_img_file, train_mask_file, valid_img_file, valid_mask_file,
               log_file, best_weight_file, end_weight_file=None, valid_img_dir=None, valid_mask_dir=None,
               backbone="resnet34", seed=42, img_size=(576, 576),
               epochs=350, freeze_encoder=True, patience=0, batchnorm=False,
               overwrite=False):
    """

    Parameters
    ----------
    train_img_dir: str
        Directory holding images in train_img_file. Use None for train_img_file that contains full paths.
    train_mask_dir: str
        Directory holding images in train_mask_file. Use None for train_mask_file that contains full paths.
    valid_img_dir: str (default None)
        Directory holding images in valid_img_file. Use None to copy from train_img_dir.
    valid_mask_dir: str (default None)
        Directory holding images in valid_mask_file. Use None to copy from train_mask_dir.
    train_img_file: str
        Full context of file containing list of train images
    train_mask_file: str
        Full context of file containing list of train mask images
    valid_img_file: str
        Full context of file containing list of validation images
    valid_mask_file: str
        Full context of file containing list of validation mask images
    log_file: str
        Full location of logging file
    best_weight_file: str
        Full location of file to save best weights
    end_weight_file: str
        Full location of file to save final weights even if not best. Set to None to ignore
    backbone: str (default 'resnet34')
        Model backbone
    seed: int (default 42)
        random number initialization value. Set to None to ignore
    img_size: tuple
        Image size in (xxx, yyy)
    epochs: int
        Maximum number of epochs for training
    freeze_encoder: bool (default=True)
        Freeze the encoder?
    patience: int (default 0)
        Patience for early stopping. If set to 0, the strict number of epochs
        will be used. If greater than zero, will stop early after N epochs
        without improvement in the loss.
    batchnorm: bool (default=False)
        Use batch norm?
    overwrite: bool (default=False)
        Overwrite existing data?
    """

    if os.path.exists(best_weight_file) and not overwrite:
        print("Weights exist, skipping training...")
        return
    else:
        verify_dir(os.path.dirname(best_weight_file))
        if end_weight_file is not None:
            verify_dir(os.path.dirname(best_weight_file))

    if valid_img_dir is None:
        valid_img_dir = train_img_dir
    if valid_mask_dir is None:
        valid_mask_dir = train_mask_dir

    # Get the list of all input/output files
    train_imgs = read_file_list(train_img_file, train_img_dir)
    train_masks = read_file_list(train_mask_file, train_mask_dir)
    valid_imgs = read_file_list(valid_img_file, valid_img_dir)
    valid_masks = read_file_list(valid_mask_file, valid_mask_dir)

    # Load and split the data
    print("==== Load and Split Data ====")
    x_train, y_train = reshape_inputs(train_imgs, train_masks, img_size)
    x_val, y_val = reshape_inputs(valid_imgs, valid_masks, img_size)

    # assert y_val.shape == x_val.shape
    # assert y_train.shape == x_train.shape
    print("x_train: ", x_train.shape)
    print("y_train: ", y_train.shape)
    print("x_val: ", x_val.shape)
    print("y_val: ", y_val.shape)

    # Preprocess the inputs via segmentation_model
    print("==== Preprocess Data ====")
    preprocess_input = sm.get_preprocessing(backbone)
    x_train = preprocess_input(x_train)
    x_val = preprocess_input(x_val)

    print("==== Augment Data ====")
    # Augment the data
    # Memory problems on this step
    # For more fixes see:
    #   https://github.com/keras-team/keras/issues/1627
    #   https://stackoverflow.com/questions/46705600/keras-fit-image-augmentations-to-training-data-using-flow-from-directory
    augment_dict = dict(
            rotation_range=30.,
            width_shift_range=0.1,
            height_shift_range=0.1,
            # shear_range=50,
            zoom_range=0.2,
            # horizontal_flip=True,
            # vertical_flip=True,
            # fill_mode='constant'
        )
    train_gen = get_augmented(
        x_train,
        y_train,
        seed=seed,
        batch_size=4,  # 2
        data_gen_args=augment_dict
    )

    # Setup outputs
    print("==== Setup Callbacks ====")
    model_filename = best_weight_file
    checkpoint_callback = ModelCheckpoint(
        model_filename,
        verbose=1,
        monitor='val_loss',
        save_best_only=True,
    )
    write_header(log_file, train_img_dir, train_mask_dir, train_img_file, train_mask_file, valid_img_file, valid_mask_file,
                 best_weight_file, end_weight_file, valid_img_dir, valid_mask_dir, backbone, seed, img_size, epochs, freeze_encoder, patience, batchnorm, augment_dict)
    csv_logger_callback = CSVLogger(log_file, append=True, separator=',')

    callbacks = [checkpoint_callback, csv_logger_callback]

    if patience > 0:
        early_callback = EarlyStopping(monitor="loss", patience=patience,
                                       restore_best_weights=True,
                                       verbose=1)
        callbacks.append(early_callback)

    # Create the model
    print("==== Create Model ====")
    model = sm.Unet(backbone,
                    encoder_weights='imagenet',
                    input_shape=(img_size[0], img_size[1], 3),
                    classes=1,
                    decoder_use_batchnorm=batchnorm,
                    encoder_freeze=freeze_encoder)
    print("==== Compile Model ====")
    model.compile(
        optimizer=SGD(lr=0.0008, momentum=0.99),
        loss=sm.losses.bce_jaccard_loss,
        metrics=[sm.metrics.iou_score],
    )

    print("==== Train ====")
    history = model.fit(
        train_gen,
        steps_per_epoch=x_train.shape[0]//4,
        epochs=epochs,
        validation_data=(x_val, y_val),
        callbacks=callbacks,
        verbose=2
    )

    if end_weight_file is not None:
        model.save_weights(end_weight_file)


if __name__ == '__main__':
    pass
    # Gebusted, come up with new demo