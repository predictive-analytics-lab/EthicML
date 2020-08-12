"""Test the loading data capability."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ethicml.data import (
    Adult,
    Compas,
    Dataset,
    Toy,
    adult,
    celeba,
    compas,
    create_data_obj,
    credit,
    crime,
    genfaces,
    german,
    group_disc_feat_indexes,
    health,
    nonbinary_toy,
    sqf,
    toy,
)
from ethicml.preprocessing import domain_split, query_dt
from ethicml.utility import DataTuple, concat_dt


def test_can_load_test_data(data_root: Path):
    """Test whether we can load test data."""
    data_loc = data_root / "toy.csv"
    data: pd.DataFrame = pd.read_csv(data_loc)
    assert data is not None


@pytest.mark.parametrize(
    "dataset,samples,x_features,discrete_features,s_features,num_sens,y_features,num_labels,name,sens_comb",
    [
        (adult(), 45222, 101, 96, 1, 2, 1, 2, "Adult Sex", False),
        (
            adult("Sex", binarize_nationality=True),
            45222,
            62,
            57,
            1,
            2,
            1,
            2,
            "Adult Sex, binary nationality",
            False,
        ),
        (adult(split="Sex"), 45222, 101, 96, 1, 2, 1, 2, "Adult Sex", False),
        (adult(split="Race"), 45222, 98, 93, 1, 5, 1, 2, "Adult Race", False),
        (adult(split="Race-Binary"), 45222, 98, 93, 1, 2, 1, 2, "Adult Race-Binary", False),
        (adult(split="Nationality"), 45222, 62, 57, 1, 41, 1, 2, "Adult Nationality", False),
        (adult(split="Education"), 45222, 86, 82, 1, 3, 1, 2, "Adult Education", False),
        (compas(), 6167, 400, 395, 1, 2, 1, 2, "Compas Sex", False),
        (compas(split="Sex"), 6167, 400, 395, 1, 2, 1, 2, "Compas Sex", False),
        (compas(split="Race"), 6167, 400, 395, 1, 2, 1, 2, "Compas Race", False),
        (compas(split="Race-Sex"), 6167, 399, 394, 1, 4, 1, 2, "Compas Race-Sex", True),
        (credit(), 30000, 26, 6, 1, 2, 1, 2, "Credit Sex", False),
        (credit(split="Sex"), 30000, 26, 6, 1, 2, 1, 2, "Credit Sex", False),
        (crime(), 1993, 136, 46, 1, 2, 1, 2, "Crime Race-Binary", False),
        (crime(split="Race-Binary"), 1993, 136, 46, 1, 2, 1, 2, "Crime Race-Binary", False),
        (german(), 1000, 57, 50, 1, 2, 1, 2, "German Sex", False),
        (german(split="Sex"), 1000, 57, 50, 1, 2, 1, 2, "German Sex", False),
        (health(), 171067, 130, 12, 1, 2, 1, 2, "Health", False),
        (health(split="Sex"), 171067, 130, 12, 1, 2, 1, 2, "Health", False),
        (nonbinary_toy(), 100, 2, 0, 1, 2, 1, 5, "NonBinaryToy", False),
        (sqf(), 12347, 145, 139, 1, 2, 1, 2, "SQF Sex", False),
        (sqf(split="Sex"), 12347, 145, 139, 1, 2, 1, 2, "SQF Sex", False),
        (sqf(split="Race"), 12347, 145, 139, 1, 2, 1, 2, "SQF Race", False),
        (sqf(split="Race-Sex"), 12347, 144, 138, 1, 4, 1, 2, "SQF Race-Sex", True),
        (toy(), 400, 10, 8, 1, 2, 1, 2, "Toy", False),
    ],
)
def test_data_shape(
    dataset,
    samples,
    x_features,
    discrete_features,
    s_features,
    num_sens,
    y_features,
    num_labels,
    name,
    sens_comb,
):
    """Test loading data."""
    data: DataTuple = dataset.load(sens_combination=sens_comb)
    assert (samples, x_features) == data.x.shape
    assert (samples, s_features) == data.s.shape
    assert (samples, y_features) == data.y.shape

    assert len(dataset.ordered_features["x"]) == x_features
    assert len(dataset.discrete_features) == discrete_features
    assert len(dataset.continuous_features) == (x_features - discrete_features)

    assert data.s.nunique()[0] == num_sens
    assert data.y.nunique()[0] == num_labels

    assert data.name == name

    data: DataTuple = dataset.load(ordered=True, sens_combination=sens_comb)
    assert (samples, x_features) == data.x.shape
    assert (samples, s_features) == data.s.shape
    assert (samples, y_features) == data.y.shape


@pytest.mark.parametrize("dataset", [Adult, Compas, Toy])
def test_deprecation_warning(dataset):
    """Test loading data."""
    with pytest.deprecated_call():  # assert that this gives a deprecation warning
        data: DataTuple = dataset().load()


def test_load_data_as_a_function(data_root: Path):
    """Test load data as a function."""
    data_loc = data_root / "toy.csv"
    data_obj: Dataset = create_data_obj(
        data_loc, s_columns=["sensitive-attr"], y_columns=["decision"]
    )
    assert data_obj is not None
    assert data_obj.feature_split["x"] == [
        "a1",
        "a2",
        "disc_1_a",
        "disc_1_b",
        "disc_1_c",
        "disc_1_d",
        "disc_1_e",
        "disc_2_x",
        "disc_2_y",
        "disc_2_z",
    ]
    assert data_obj.feature_split["s"] == ["sensitive-attr"]
    assert data_obj.feature_split["y"] == ["decision"]
    assert len(data_obj) == 400


def test_joining_2_load_functions(data_root: Path):
    """Test joining 2 load functions."""
    data_loc = data_root / "toy.csv"
    data_obj: Dataset = create_data_obj(
        data_loc, s_columns=["sensitive-attr"], y_columns=["decision"]
    )
    data: DataTuple = data_obj.load()
    assert (400, 10) == data.x.shape
    assert (400, 1) == data.s.shape
    assert (400, 1) == data.y.shape


def test_load_compas_feature_length():
    """Test load compas feature length."""
    data: DataTuple = compas().load()
    assert len(compas().ordered_features["x"]) == 400
    assert len(compas().discrete_features) == 395
    assert len(compas().continuous_features) == 5
    disc_feature_groups = compas().disc_feature_groups
    assert disc_feature_groups is not None
    assert len(disc_feature_groups["c-charge-desc"]) == 389
    assert data.s.shape == (6167, 1)
    assert data.y.shape == (6167, 1)


def test_load_adult_explicitly_sex():
    """Test load adult explicitly sex."""
    adult_sex = adult("Sex")
    data: DataTuple = adult_sex.load()
    assert (45222, 101) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert (45222, 1) == data.y.shape
    assert adult_sex.disc_feature_groups is not None
    assert "sex" not in adult_sex.disc_feature_groups
    assert "salary" not in adult_sex.disc_feature_groups


def test_load_adult_race():
    """Test load adult race."""
    adult_race = adult("Race")
    data: DataTuple = adult_race.load()
    assert (45222, 98) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert data.s.nunique()[0] == 5
    assert (45222, 1) == data.y.shape
    assert adult_race.disc_feature_groups is not None
    assert "race" not in adult_race.disc_feature_groups
    assert "salary" not in adult_race.disc_feature_groups


def test_load_adult_race_sex():
    """Test load of split combinatin that doesn't exist yet."""
    with pytest.raises(AssertionError):
        data: DataTuple = adult("Race-Sex").load()


def test_race_feature_split():
    """Test race feature split."""
    adult_data: Dataset = adult(split="Custom")
    adult_data = replace(
        adult_data,
        sens_attrs=["race_White"],
        s_prefix=["race"],
        class_labels=["salary_>50K"],
        class_label_prefix=["salary"],
    )

    data: DataTuple = adult_data.load()

    assert (45222, 98) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert (45222, 1) == data.y.shape


def test_load_adult_drop_native():
    """Test load adult drop native."""
    adult_data = adult("Sex", binarize_nationality=True)
    assert adult_data.name == "Adult Sex, binary nationality"
    assert "native-country_United-States" in adult_data.discrete_features
    assert "native-country_Canada" not in adult_data.discrete_features

    # with dummies
    data = adult_data.load(ordered=True)
    assert (45222, 62) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert (45222, 1) == data.y.shape
    assert "native-country_United-States" in data.x.columns
    # the dummy feature *is* in the actual dataframe:
    assert "native-country_not_United-States" in data.x.columns
    assert "native-country_Canada" not in data.x.columns
    native_cols = data.x[["native-country_United-States", "native-country_not_United-States"]]
    assert (native_cols.sum(axis="columns") == 1).all()

    # with dummies, not ordered
    data = adult_data.load(ordered=False)
    assert (45222, 62) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert (45222, 1) == data.y.shape
    assert "native-country_United-States" in data.x.columns
    # the dummy feature *is* in the actual dataframe:
    assert "native-country_not_United-States" in data.x.columns
    assert "native-country_Canada" not in data.x.columns
    native_cols = data.x[["native-country_United-States", "native-country_not_United-States"]]
    assert (native_cols.sum(axis="columns") == 1).all()


def test_load_adult_education():
    """Test load adult education."""
    adult_data = adult("Education")
    assert adult_data.name == "Adult Education"
    assert "education_HS-grad" in adult_data.sens_attrs
    assert "education_other" in adult_data.sens_attrs
    assert "education_Masters" not in adult_data.sens_attrs

    # ordered
    data = adult_data.load(ordered=True)
    assert (45222, 86) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert data.s.nunique()[0] == 3
    assert (45222, 1) == data.y.shape
    assert "education" in data.s.columns

    # not ordered
    data = adult_data.load()
    assert (45222, 86) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert data.s.nunique()[0] == 3
    assert (45222, 1) == data.y.shape
    assert "education" in data.s.columns


def test_load_adult_education_drop():
    """Test load adult education."""
    adult_data = adult("Education", binarize_nationality=True)
    assert adult_data.name == "Adult Education, binary nationality"
    assert "education_HS-grad" in adult_data.sens_attrs
    assert "education_other" in adult_data.sens_attrs
    assert "education_Masters" not in adult_data.sens_attrs

    # ordered
    data = adult_data.load(ordered=True)
    assert (45222, 47) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert data.s.nunique()[0] == 3
    assert (45222, 1) == data.y.shape
    assert "education" in data.s.columns

    # not ordered
    data = adult_data.load()
    assert (45222, 47) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert data.s.nunique()[0] == 3
    assert (45222, 1) == data.y.shape
    assert "education" in data.s.columns


def test_additional_columns_load(data_root: Path):
    """Test additional columns load."""
    data_loc = data_root / "adult.csv.zip"
    data_obj: Dataset = create_data_obj(
        data_loc,
        s_columns=["race_White"],
        y_columns=["salary_>50K"],
        additional_to_drop=["race_Black", "salary_<=50K"],
    )
    data: DataTuple = data_obj.load()

    assert (45222, 102) == data.x.shape
    assert (45222, 1) == data.s.shape
    assert (45222, 1) == data.y.shape


def test_domain_adapt_adult():
    """Test domain adapt adult."""
    data: DataTuple = adult().load()
    train, test = domain_split(
        datatup=data,
        tr_cond="education_Masters == 0. & education_Doctorate == 0.",
        te_cond="education_Masters == 1. | education_Doctorate == 1.",
    )
    assert (39106, 101) == train.x.shape
    assert (39106, 1) == train.s.shape
    assert (39106, 1) == train.y.shape

    assert (6116, 101) == test.x.shape
    assert (6116, 1) == test.s.shape
    assert (6116, 1) == test.y.shape

    data = adult().load()
    train, test = domain_split(
        datatup=data, tr_cond="education_Masters == 0.", te_cond="education_Masters == 1."
    )
    assert (40194, 101) == train.x.shape
    assert (40194, 1) == train.s.shape
    assert (40194, 1) == train.y.shape

    assert (5028, 101) == test.x.shape
    assert (5028, 1) == test.s.shape
    assert (5028, 1) == test.y.shape

    data = adult().load()
    train, test = domain_split(
        datatup=data,
        tr_cond="education_Masters == 0. & education_Doctorate == 0. & education_Bachelors == 0.",
        te_cond="education_Masters == 1. | education_Doctorate == 1. | education_Bachelors == 1.",
    )
    assert (23966, 101) == train.x.shape
    assert (23966, 1) == train.s.shape
    assert (23966, 1) == train.y.shape

    assert (21256, 101) == test.x.shape
    assert (21256, 1) == test.s.shape
    assert (21256, 1) == test.y.shape


def test_query():
    """Test query."""
    x: pd.DataFrame = pd.DataFrame(columns=["0a", "b"], data=[[0, 1], [2, 3], [4, 5]])
    s: pd.DataFrame = pd.DataFrame(columns=["c="], data=[[6], [7], [8]])
    y: pd.DataFrame = pd.DataFrame(columns=["d"], data=[[9], [10], [11]])
    data = DataTuple(x=x, s=s, y=y, name="test_data")
    selected = query_dt(data, "_0a == 0 & c_eq_ == 6 & d == 9")
    pd.testing.assert_frame_equal(selected.x, x.head(1))
    pd.testing.assert_frame_equal(selected.s, s.head(1))
    pd.testing.assert_frame_equal(selected.y, y.head(1))


def test_concat():
    """Test concat."""
    x: pd.DataFrame = pd.DataFrame(columns=["a"], data=[[1]])
    s: pd.DataFrame = pd.DataFrame(columns=["b"], data=[[2]])
    y: pd.DataFrame = pd.DataFrame(columns=["c"], data=[[3]])
    data1 = DataTuple(x=x, s=s, y=y, name="test_data")
    x = pd.DataFrame(columns=["a"], data=[[4]])
    s = pd.DataFrame(columns=["b"], data=[[5]])
    y = pd.DataFrame(columns=["c"], data=[[6]])
    data2 = DataTuple(x=x, s=s, y=y, name="test_tuple")
    data3 = concat_dt([data1, data2], axis="index", ignore_index=True)
    pd.testing.assert_frame_equal(data3.x, pd.DataFrame(columns=["a"], data=[[1], [4]]))
    pd.testing.assert_frame_equal(data3.s, pd.DataFrame(columns=["b"], data=[[2], [5]]))
    pd.testing.assert_frame_equal(data3.y, pd.DataFrame(columns=["c"], data=[[3], [6]]))


def test_group_prefixes():
    """Test group prefixes."""
    names = ["a_asf", "a_fds", "good_lhdf", "good_dsdw", "sas"]
    grouped_indexes = group_disc_feat_indexes(names, prefix_sep="_")

    assert len(grouped_indexes) == 3
    assert grouped_indexes[0] == slice(0, 2)
    assert grouped_indexes[1] == slice(2, 4)
    assert grouped_indexes[2] == slice(4, 5)


def test_celeba():
    """Test celeba."""
    celeba_data, _ = celeba(download_dir="non-existent")
    assert celeba_data is None  # data should not be there
    celeba_data, _ = celeba(download_dir="non-existent", check_integrity=False)
    assert celeba_data is not None
    data = celeba_data.load(map_to_binary=True)

    assert celeba_data.name == "CelebA, s=[Male], y=Smiling"

    assert (202599, 39) == data.x.shape
    assert (202599, 1) == data.s.shape
    assert (202599, 1) == data.y.shape
    assert len(data) == len(celeba_data)

    assert data.x["filename"].iloc[0] == "000001.jpg"


def test_celeba_multi_s():
    """Test celeba w/ multi S."""
    celeba_data, _ = celeba(
        sens_attr=["Young", "Male"], download_dir="non-existent", check_integrity=False
    )
    assert celeba_data is not None
    data = celeba_data.load(sens_combination=True, map_to_binary=True)

    assert celeba_data.name == "CelebA, s=[Young, Male], y=Smiling"
    assert celeba_data.combination_multipliers == {"Young": 1, "Male": 2}

    assert np.unique(data.s.to_numpy()).tolist() == [0, 1, 2, 3]
    assert data.s.columns[0] == "Young,Male"
    assert (202599, 38) == data.x.shape
    assert (202599, 1) == data.s.shape
    assert (202599, 1) == data.y.shape
    assert len(data) == len(celeba_data)

    assert data.x["filename"].iloc[0] == "000001.jpg"


def test_genfaces():
    """Test genfaces."""
    gen_faces, _ = genfaces(download_dir="non-existent")
    assert gen_faces is None  # data should not be there
    gen_faces, _ = genfaces(download_dir="non-existent", check_integrity=False)
    assert gen_faces is not None
    data = gen_faces.load()

    assert gen_faces.name == "GenFaces, s=gender, y=emotion"

    assert (148285, 18) == data.x.shape
    assert (148285, 1) == data.s.shape
    assert (148285, 1) == data.y.shape
    assert len(data) == len(gen_faces)

    assert data.x["filename"].iloc[0] == "5e011b2e7b1b30000702aa59.jpg"
