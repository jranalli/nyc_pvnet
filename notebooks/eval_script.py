from model.dataset_manipulation import test_train_valid_split, make_combo_dataset_txt
from model.train_model import train_unet
from model.eval_model import eval_model
import os
import gc


def run():
    # #### SETTINGS #####

    # ## Global ##
    dataroot = os.path.join("d:", "data", 'solardnn')

    test_sets = ["CA-F", "CA-S", "FR-G", "FR-I", "DE-G", "NY-Q"]
    train_sets = test_sets + ["CMB-6", "CMB-5A"]
    combo_sets = {"CMB-6": ["CA-F", "CA-S", "FR-G", "FR-I", "DE-G", "NY-Q"],
                  "CMB-5A": ["CA-S", "FR-G", "FR-I", "DE-G", "NY-Q"], # Excludes CA-F
                  }

    # ## Dataset ##
    do_build_datasets = True
    splits = [0.2, 0.72, 0.08]  # Test, Train, Valid
    myseeds = [42]
    n_set = 1000

    # ## Train ##
    do_train_models = True
    mybackbones = ["resnet34"]
    mysize = 576
    epochs = 200
    patience = 10
    norm = True
    freeze = True
    model_revs = ["1"]

    # ## Test ##
    do_test_models = True
    do_plots = False
    test_weights = 'best'

    # #### END SETTINGS ####





    print("\n\n===== BUILD PATHS =====\n\n")
    paths = configure_paths(dataroot, train_sets, myseeds, mybackbones, model_revs, test_sets)

    if do_build_datasets:
        print("\n\n===== BUILD DATASETS =====\n\n")
        build_datasets(paths, train_sets, myseeds, n_set, splits, combo_sets)

    if do_train_models:
        print("\n\n===== TRAINING =====\n\n")
        train_models(paths, train_sets, myseeds, mybackbones, model_revs, mysize, epochs, freeze, patience, norm)

    if do_test_models:
        print("\n\n===== TESTING =====\n\n")
        eval_models(paths, train_sets, myseeds, mybackbones, model_revs, test_sets, mysize, norm, test_weights, do_plots)


def configure_paths(data_root_dir, train_sets, seeds, backbones, model_revs, test_sets):
    """
    Generate a paths data object holding the conventional paths for the project.

    Nested dicts of paths[train_set][seed][backbone][model_rev][test_set] with things at various levels
        [train_set]
            Stores directory paths germane to the different training datasets
            - tiles: the root tile directory for the dataset.  e.g. d:\solardnn\NY-Q\tiles
            - img_root: the root image directory for dataset. e.g. d:\solardnn\NY-Q\tiles\img
            - mask_root: the root mask directory for dataset. e.g. d:\solardnn\NY-Q\tiles\mask
            - model_out_root: directory where models should be saved. e.g. d:\solardnn\NY-Q\models
            - prediction_root: directory for predictions when the model is tested. e.g. d:\solardnn\NY-Q\predictions
        [seed]
            Stores the various dataset definition files. These will be located in the tiles directory for the training set.
            - test_im: Location of dataset definition file for test images. e.g. d:\solardnn\NY-Q\tiles\test_im_42.txt
            - test_mask: Location of dataset definition file for test masks. e.g. d:\solardnn\NY-Q\tiles\test_mask_42.txt
            - train_im: Location of dataset definition file for train images. e.g. d:\solardnn\NY-Q\tiles\train_im_42.txt
            - train_mask: Location of dataset definition file for train masks. e.g. d:\solardnn\NY-Q\tiles\train_mask_42.txt
            - valid_im: Location of dataset definition file for valid images. e.g. d:\solardnn\NY-Q\tiles\valid_im_42.txt
            - valid_mask: Location of dataset definition file for valid masks. e.g. d:\solardnn\NY-Q\tiles\valid_mask_42.txt
        backbone:
            Holder for next level
        revision:
            Stores the info about the trained model. All model outputs are stored together in the models directory for
            the training set. The model filenames differentiate them.
            - best_weights: Location of best weights file. e.g. d:\solardnn\NY-Q\models\NY-Q_resnet34_42_v1_weights_best.h5
            - final_weights: Location of final weights file. e.g. d:\solardnn\NY-Q\models\NY-Q_resnet34_42_v1_weights_final.h5
            - train_log: Location of log file from training. e.g. d:\solardnn\NY-Q\models\NY-Q_resnet34_42_v1_trainlog.csv
        test_set:
            Stores info about the outputs when we test a model. Stored nested below the predictions root dir for the
            training set. The subdir name will always be \{train_set}_{backbone}_{seed}_v{model_rev}_predicting_{test_set}\
            - prediction_dir: The location of the prediction masks dir for the test set.
                e.g. d:\solardnn\NY-Q\predictions\NY-Q_resnet34_42_v1_predicting_CA-F\pred_masks
            - plot dir: The location of plot files if they're generated.
                e.g. d:\solardnn\NY-Q\predictions\NY-Q_resnet34_42_v1_predicting_CA-F\plots
            - result file: The location of the datafile for the prediction summary
                e.g. d:\solardnn\NY-Q\predictions\NY-Q_resnet34_42_v1_predicting_CA-F\NY-Q_resnet34_42_v1_predicting_CA-F_data.csv


    Parameters
    ----------
    data_root_dir: str
        Root directory for all the data. Sites should be subdirs here and must contain subdirectories of tiles, images and masks.
        e.g. d:\data\solardnn\{SITE}\tiles\img   and   d:\data\solardnn\{SITE}\tiles\mask
    train_sets: list[str]
        List of strings representing all the training sets to consider. e.g. ['CA-F','NY-Q','CMB-6']
    seeds: list[int]
        List of all seeds to consider. e.g. [42]
    backbones: list[str]
        List of all backbones to run. e.g. ['resnet34','resnet50']
    model_revs: list[str]
        List of revision flags to add to the models. Note that these will be appended to filenames but will have no impact on the runs.
        Technically could probably be any type.
        e.g. [1]
    test_sets: list[str]
        List of strings representing all the test data sets to consider. These should never include combos.
        e.g. ['CA-F','NY-Q']

    Returns
    -------
    Deeply nested dictionary following conventions notated above.
        paths[train_set][seed][backbone][model_rev][test_set]
    """
    paths = {}

    for train_set in train_sets:
        paths[train_set] = {}
        siteroot = os.path.join(data_root_dir, train_set)
        tileroot = os.path.join(data_root_dir, train_set, "tiles")
        modeloutroot = os.path.join(siteroot, "models")
        predictionroot = os.path.join(siteroot, "predictions")

        if "CMB" in train_set:  # let the img_root be pulled from the file
            img_root = None
            mask_root = None
        else:
            img_root = os.path.join(tileroot, f"img")
            mask_root = os.path.join(tileroot, f"mask")

        paths[train_set]['tiles'] = tileroot
        paths[train_set]['img_root'] = img_root
        paths[train_set]['mask_root'] = mask_root
        paths[train_set]['model_out_root'] = modeloutroot
        paths[train_set]['prediction_root'] = predictionroot

        for seed in seeds:
            paths[train_set][seed] = {}

            paths[train_set][seed]['test_im'] = os.path.join(tileroot, f"test_img_{seed}.txt")
            paths[train_set][seed]['test_mask'] = os.path.join(tileroot, f"test_mask_{seed}.txt")
            paths[train_set][seed]['train_im'] = os.path.join(tileroot, f"train_img_{seed}.txt")
            paths[train_set][seed]['train_mask'] = os.path.join(tileroot, f"train_mask_{seed}.txt")
            paths[train_set][seed]['valid_im'] = os.path.join(tileroot, f"valid_img_{seed}.txt")
            paths[train_set][seed]['valid_mask'] = os.path.join(tileroot, f"valid_mask_{seed}.txt")

            for backbone in backbones:
                paths[train_set][seed][backbone] = {}
                for model_rev in model_revs:
                    paths[train_set][seed][backbone][model_rev] = {}
                    paths[train_set][seed][backbone][model_rev]['best_weights'] = os.path.join(modeloutroot,
                                                                                               f"{train_set}_{backbone}_{seed}_v{model_rev}_weights_best.h5")
                    paths[train_set][seed][backbone][model_rev]['final_weights'] = os.path.join(modeloutroot,
                                                                                                f"{train_set}_{backbone}_{seed}_v{model_rev}_weights_final.h5")
                    paths[train_set][seed][backbone][model_rev]['train_log'] = os.path.join(modeloutroot,
                                                                                            f"{train_set}_{backbone}_{seed}_v{model_rev}_trainlog.csv")

                    for test_set in test_sets:
                        paths[train_set][seed][backbone][test_set] = {}
                        paths[train_set][seed][backbone][test_set]['prediction_dir'] = os.path.join(predictionroot,
                                                                                                    f"{train_set}_{backbone}_{seed}_v{model_rev}_predicting_{test_set}",
                                                                                                    "pred_masks")
                        paths[train_set][seed][backbone][test_set]['plot_dir'] = os.path.join(predictionroot,
                                                                                              f"{train_set}_{backbone}_{seed}_v{model_rev}_predicting_{test_set}",
                                                                                              "plots")
                        paths[train_set][seed][backbone][test_set]['result_file'] = os.path.join(predictionroot,
                                                                                                 f"{train_set}_{backbone}_{seed}_v{model_rev}_predicting_{test_set}",
                                                                                                 f"{train_set}_{backbone}_{seed}_v{model_rev}_predicting_{test_set}_data.csv")

    return paths


def build_datasets(paths, train_sets, seeds, n_set, test_train_valid, combo_sets=None):
    """
    Wrapper for building the test/train/validation subsets that are listed in text files.

    Some special note is warranted for combo datasets. They must use the word CMB in the train_set identifier. If CMB
    datasets are present, the optional parameter `combo_sets` must be provided. It should be a dictionary, keyed by the
    train_set identifier for the combo set, and then valued as a list of other train_sets to use. All values specified
    within the `combo_set` must be listed as a train_set in `paths`.
    e.g.
        train_sets = ["NY-Q", "DE-G", "FR-I", "CMB2"]
        combo_sets = {"CMB2": ["NY-Q", "FR-I"]}

    Parameters
    ----------
    paths: nested dict
        Output from configure_paths(). See docs for configure_paths() for a description.
    train_sets: list[str]
        List of strings representing all the training sets to consider. e.g. ['CA-F','NY-Q','CMB-6']
    seeds: list[int]
        List of all seeds to consider. e.g. [42]
    n_set: int
        The # of images to include in the total dataset. Can be set to None to generate list of all files (not compatible
        combo datasets).
    test_train_valid: list[float, float, float]
        floats representing the test/train/validation split. e.g. [0.1, 0.8, 0.1]
    combo_sets: dict
        dictionary defining any CMB datasets. See full description for info.
    """
    for train_set in train_sets:
        for seed in seeds:
            if "CMB" in train_set:
                try:
                    these_sets = combo_sets[train_set]

                    # File names
                    tr_im_f = paths[train_set][seed]['train_im']
                    tr_m_f = paths[train_set][seed]['train_mask']
                    v_im_f = paths[train_set][seed]['valid_im']
                    v_m_f = paths[train_set][seed]['valid_mask']

                    # Paths for the base sets
                    all_img_rt = [paths[someset]['img_root'] for someset in these_sets]
                    all_mask_rt = [paths[someset]['mask_root'] for someset in these_sets]

                    # train img
                    all_tr_i_fs = [paths[someset][seed]['train_im'] for someset in these_sets]
                    make_combo_dataset_txt(all_tr_i_fs, tr_im_f, all_img_rt, total_imgs=int(n_set * test_train_valid[1]),
                                           seed=seed)

                    # train mask
                    all_tr_m_fs = [paths[someset][seed]['train_mask'] for someset in these_sets]
                    make_combo_dataset_txt(all_tr_m_fs, tr_m_f, all_mask_rt, total_imgs=int(n_set * test_train_valid[1]),
                                           seed=seed)

                    # val img
                    all_v_i_fs = [paths[someset][seed]['valid_im'] for someset in these_sets]
                    make_combo_dataset_txt(all_v_i_fs, v_im_f, all_img_rt, total_imgs=int(n_set * test_train_valid[2]), seed=seed)

                    # val mask
                    all_v_m_fs = [paths[someset][seed]['valid_mask'] for someset in these_sets]
                    make_combo_dataset_txt(all_v_m_fs, v_m_f, all_mask_rt, total_imgs=int(n_set * test_train_valid[2]), seed=seed)
                except KeyError:
                    print(f"combo_sets does not contain a specifier for {train_set}. Skipping...")
            else:
                imdir = paths[train_set]['img_root']
                maskdir = paths[train_set]['mask_root']
                tiledir = paths[train_set]['tiles']
                test_train_valid_split(imdir, maskdir, tiledir, test_train_valid=test_train_valid, seed=seed, n_set=n_set)


def train_models(paths, train_sets, seeds, backbones, model_revs, img_size, epochs, freeze_encoder, patience, batchnorm):
    """
    Wrapper to help calling the training for multiple models at once

    Parameters
    ----------
    paths: nested dict
        Output from configure_paths(). See docs for configure_paths() for a description.
    train_sets: list[str]
        List of strings representing all the training sets to consider. e.g. ['CA-F','NY-Q','CMB-6']
    seeds: list[int]
        List of all seeds to consider. e.g. [42]
    backbones: list[str]
        List of all backbones to run. e.g. ['resnet34','resnet50']
    model_revs: list[str]
        List of revision flags to add to the models. Note that these will be appended to filenames but will have no impact on the runs.
        Technically could probably be any type.
        e.g. [1]
    img_size: int
        Size images should be resized to. Images will be resized to (img_size x img_size)
    epochs: int
        Max number of epochs
    freeze_encoder: bool
        Should the encoder be frozen?
    patience: int
        Patience that should be used in early stopping. Set to 0 to run for full epochs.
    batchnorm: bool
        Should batch normalization be used?
    """
    for train_set in train_sets:
        for seed in seeds:
            for backbone in backbones:
                for model_rev in model_revs:
                    print(f"Training: \nSet: {train_set}\nSeed: {seed}\nBackbone: {backbone}\nRev: v{model_rev}\n")

                    imdir = paths[train_set]['img_root']
                    maskdir = paths[train_set]['mask_root']
                    tr_im_f = paths[train_set][seed]['train_im']
                    tr_m_f = paths[train_set][seed]['train_mask']
                    v_im_f = paths[train_set][seed]['valid_im']
                    v_m_f = paths[train_set][seed]['valid_mask']
                    best_wgt = paths[train_set][seed][backbone][model_rev]['best_weights']
                    final_wgt = paths[train_set][seed][backbone][model_rev]['final_weights']
                    log = paths[train_set][seed][backbone][model_rev]['train_log']

                    train_unet(imdir, maskdir, tr_im_f, tr_m_f, v_im_f, v_m_f, log_file=log, best_weight_file=best_wgt,
                               end_weight_file=final_wgt, backbone=backbone, seed=seed, img_size=(img_size, img_size),
                               epochs=epochs, freeze_encoder=freeze_encoder, patience=patience, batchnorm=batchnorm)

                    gc.collect()


def eval_models(paths, train_sets, seeds, backbones, model_revs, test_sets, img_size, batchnorm, weight_type, gen_plots=False):
    """
    Wrapper to help perform the model evaluation for a large set of models

    Parameters
    ----------
    paths: nested dict
        Output from configure_paths(). See docs for configure_paths() for a description.
    train_sets: list[str]
        List of strings representing all the training sets to consider. e.g. ['CA-F','NY-Q','CMB-6']
    seeds: list[int]
        List of all seeds to consider. e.g. [42]
    backbones: list[str]
        List of all backbones to run. e.g. ['resnet34','resnet50']
    model_revs: list[str]
        List of revision flags to add to the models. Note that these will be appended to filenames but will have no impact on the runs.
        Technically could probably be any type.
        e.g. [1]
    test_sets: list[str]
        List of strings representing all the test data sets to consider. These should never include combos.
        e.g. ['CA-F','NY-Q']
    img_size: int
        Size images should be resized to. Images will be resized to (img_size x img_size)
    batchnorm: bool
        Should batch normalization be used?
    weight_type: str
        One of 'best' or 'final'. Which weights file should be read for the trained model.
    gen_plots: bool (default False)
        Should plots be generated?
    """
    for train_set in train_sets:
        for seed in seeds:
            for backbone in backbones:
                for model_rev in model_revs:
                    for test_set in test_sets:

                        tst_im_f = paths[train_set][seed]['test_im']
                        tst_m_f = paths[train_set][seed]['test_mask']

                        imdir = paths[train_set]['img_root']
                        maskdir = paths[train_set]['mask_root']

                        if weight_type == 'best':
                            wgt_file = paths[train_set][seed][backbone][model_rev]['best_weights']
                        elif weight_type == 'final':
                            wgt_file = paths[train_set][seed][backbone][model_rev]['final_weights']
                        else:
                            print("Weights not found!")
                            continue

                        pred_dir = paths[train_set][seed][backbone][test_set]['prediction_dir']
                        res_file = paths[train_set][seed][backbone][test_set]['result_file']

                        if gen_plots:
                            plot_dir = paths[train_set][seed][backbone][test_set]['plot_dir']
                        else:
                            plot_dir = None

                        eval_model(imdir, maskdir, tst_im_f, tst_m_f, wgt_file, res_file, pred_dir, plot_dir,
                                   backbone=backbone, img_size=(img_size, img_size), batchnorm=batchnorm)

                        gc.collect()


if __name__ == "__main__":
    run()
