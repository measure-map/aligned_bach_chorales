<!-- TOC -->
* [The Aligned Bach Chorales](#the-aligned-bach-chorales)
  * [Included data](#included-data)
    * [`aligned_files.csv`](#alignedfilescsv)
    * [`data`](#data)
    * [`code`](#code)
      * [`01_prepare_metadata.py`](#01preparemetadatapy)
      * [`02_make_pcvs.py`](#02makepcvspy-)
      * [`03_compare_pcvs.py`](#03comparepcvspy)
  * [Getting the data](#getting-the-data)
    * [Cloning without original datasets](#cloning-without-original-datasets)
    * [Cloning with original datasets](#cloning-with-original-datasets)
<!-- TOC -->

# The Aligned Bach Chorales

This repository aligns three datasets representing the 371 chorales composed by J.S. Bach and compiled by Johann
Philipp Kirnberger and Carl Philipp Emanuel Bach. The datasets are:

| key | repository                                     | submodule      | description                                                                                                                              |
|-----|------------------------------------------------|----------------|------------------------------------------------------------------------------------------------------------------------------------------|
| cap | https://github.com/DCMLab/bach_chorales        | DCMLab_cap     | Capella files by Ulrich Kaiser converted to MuseScore 3.                                                                                 |
| krn | https://github.com/craigsapp/bach-370-chorales | craigsapp_krn  | Humdrum **kern files by Craig Stuart Sapp, converted to musicxml.                                                                        |
| xml | https://github.com/MarkGotham/Chorale-Corpus   | MarkGotham_xml | From the MuseScore user [x_x0_0](https://musescore.com/user/11015626/sets/5105738), split into individual musicxml files by Mark Gotham. |

## Included data

### `aligned_files.csv`

The file aligns the file names from the three datasets with the Riemenschneider catalog:

| Riemenschneider | krn_file    | dcml_file                                               | xml_file            |
|-----------------|-------------|---------------------------------------------------------|---------------------|
| 1               | chor001.krn | 001 Aus meines Herzens Grunde.mscx                      | 001/short_score.mxl |
| 2               | chor002.krn | 002 Ich danke dir, lieber Herre.mscx                    | 002/short_score.mxl |
| 3               | chor003.krn | 003 Ach Gott, vom Himmel sieh darein.mscx               | 003/short_score.mxl |
| 4               | chor004.krn | 004 Es ist das Heil uns kommen her.mscx                 | 004/short_score.mxl |
| 5               | chor005.krn | 005 An Wasserflüssen Babylon.mscx                       | 005/short_score.mxl |
| 6               | chor006.krn | 007 Christus, der ist mein Leben.mscx                   | 007/short_score.mxl |
| 7               | chor007.krn | 006 Nun lob, mein Seel, den Herren.mscx                 | 006/short_score.mxl |
| 8               | chor008.krn | 008 Freuet euch, ihr Christen alle.mscx                 | 008/short_score.mxl |
| 9               | chor009.krn | 009 Ermuntre dich, mein schwacher Geist.mscx            | 009/short_score.mxl |
| 10              | chor010.krn | 010 Aus tiefer Not schrei ich zu dir.mscx               | 010/short_score.mxl |

### `data`

The `data` directory contains the scores from all three datasets converted to MuseScore 4 `.mscz` format. 
The paths are:

* `data/craigsapp_krn/musicxml`
* `data/DCMLab_cap/MS3`
* `data/MarkGotham_xml/Bach,_Johann_Sebastian/Chorales`

In the latter case, the original scores all have the same filename (`short_score.xml`) and were 
have been renamed from `###/short_score.xml` =>  `###.mscz` (where `###` is the three-digit, zero-filled corrected
CPE number, see below) to allow for processing with [ms3](https://pypi.org/project/ms3/).

Each of the three directories in `data` furthermore contains two folders with the TSV files produced by ms3:

* `measures`: One tabular file per chorale with one row per measure.
* `notes`: One tabular file per chorale with one row per note head.

The meaning of the columns is explained in the [ms3 documentation](https://ms3.readthedocs.io/columns).

### `code`

The Python code relies only on the `data` folder, not on the submodules with the original datasets. It can be run
in two ways (commands assume current working directory is `code`):

* As a standalone script, e.g. `python3 03_compare_pcvs.py`. Requires installing the dependencies in `requirements.txt`
  (`pip install -r requirements.txt`).
* As a Jupyter notebook. Require installing the dependencies in `requirements_jupytext.txt`   
  (`pip install -r requirements_jupytext.txt`) and opening the respective `.py` file in Jupyter
  ([HowTo](https://jupytext.readthedocs.io/en/latest/paired-notebooks.html#how-to-open-scripts-with-either-the-text-or-notebook-view-in-jupyter))

Each of the scripts produces CSV files used by the subsequent ones:

#### `01_prepare_metadata.py`

* Outputs: `riemenschneider.csv` (& `krn_metadata.csv` & `krn_metadata_dtypes.csv`)
* Starts off with the comprehensive overview of chorales from http://www.bach-chorales.com/BachChoraleTable.htm
* From this, creates numerical columns `Riemenschneider <= R` and `CPE <= B`
* Sets `Riemenschneider` as index, discarding all additional rows pertaining to chorales not in the catalogue.
* Adds the filenames from the three datasets to be aligned, by simply pretending they were following the
  Riemenschneider numbers already. In other words, this table does not correspond to a correct alignment of the music.

#### `02_make_pcvs.py` 

* Outputs: `cap.csv`, `krn.csv`, `xml.csv`

Each of the three files contains one pitch-class vectors per chorale in the respective dataset, e.g.:

|     | -6  | -5  | -4  | -3   | -2   | -1   | 0    | 1    | 2    | 3    | 4    | 5    | 6    | 7    | 8    | 9    | 10   | 11  | 12  |
|-----|-----|-----|-----|------|------|------|------|------|------|------|------|------|------|------|------|------|------|-----|-----|
| 001 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 0.5  | 5.0  | 4.0  | 1.0  | 2.0  | 2.5  | 1.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 002 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 1.0  | 5.0  | 2.0  | 1.5  | 5.0  | 3.5  | 1.0  | 1.0  | 0.0  | 0.0 | 0.0 |
| 003 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 2.5  | 0.0  | 1.5  | 5.0  | 5.0  | 3.5  | 0.0  | 0.0  | 2.5  | 0.0  | 0.0  | 0.0 | 0.0 |
| 004 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 1.0  | 1.5  | 4.5  | 5.5  | 3.0  | 0.0  | 3.0  | 1.5  | 0.0  | 0.0 | 0.0 |
| 005 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 2.5  | 4.5  | 3.5  | 1.5  | 3.0  | 2.5  | 2.5  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 006 | 0.0 | 0.0 | 0.0 | 1.0  | 1.0  | 6.0  | 4.0  | 2.0  | 2.0  | 3.0  | 1.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 007 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 4.0  | 2.0  | 0.0  | 4.0  | 5.0  | 1.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 008 | 0.0 | 2.0 | 4.0 | 1.0  | 3.5  | 10.5 | 6.5  | 2.0  | 0.0  | 1.0  | 1.5  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 009 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 1.0  | 4.0  | 4.0  | 2.5  | 2.5  | 2.5  | 3.0  | 0.5  | 0.0  | 0.0  | 0.0  | 0.0 | 0.0 |
| 010 | 0.0 | 0.0 | 0.0 | 0.0  | 0.0  | 0.0  | 3.5  | 1.5  | 4.5  | 5.5  | 6.5  | 6.0  | 1.5  | 0.0  | 3.0  | 0.0  | 0.0  | 0.0 | 0.0 |

* The files are contained in a subfolder corresponding to the configuration set in the notebook/script.
  * `tpc_2_pcvs` is the setting used in `03_compare_pcvs.py`. Each pitch-class vector corresponds to the accumulated 
    duration (in quarter notes) of each tonal pitch class (TPC, an integer such that 0=C, 1=G, -1=F, -2=Bb etc.) 
    occurring in the dataset, in the first two encoded measures (+ anacrusis if any) of one chorale.
  * `tpc_pcvs` The same type of pitch-class vectors, but for the complete chorale. Included for convenience or further
    comparisons between the aligned chorales for detection of encoding errors or differences between the chorale
    settings.
* The first column corresponds to the `Riemenschneider` index in the `riemenschneider.csv`, as explained in the 
  previous section. That is to say, `krn.csv` is correctly aligned with the catalogue, the other two files are not,
  even if they use the same index.
* `krn.csv` omits R. 150 (because it's not 4-voice) and `cap.csv` is missing R. 50, 59, 103, 217, 238, 272, 325, 334, 
  343, and 351

#### `03_compare_pcvs.py`

The notebook represents a tool that has evolved in the process of aligning the datasets. It computes the summed
absolute error between corresponding pitch-class vectors and has functionality for finding the best-matching piece(s)
from dataset B for a single pitch-class vector from dataset A.

Outputs:
* `groundtruth_pcvs.csv`: The pitch-class vectors, as described in the previous section, resulting from the alignment
  of the `cap` with the `krn` dataset. It takes for granted the 337 vectors that matched perfectly between the datasets.
  For the 34 remaining ones that had slight divergences, the code contains the result of a manual comparison with the
  original print edition ([Breitkopf & Härtel, Leipzig 1871](https://imslp.org/wiki/Special:ReverseLookup/495149), 
  included in the folder `pdf`). The pitch-class vector corresponding to the original print was adopted.
* `../aligned_files.csv` as explained above.

## Getting the data

The repositories are included as submodules in this repository and the data pipeline can be re-run if one of them 
is updated. 

### Cloning without original datasets

If you clone this repository via `git clone https://github.com/johentsch/aligned_bach_chorales.git`, you will get
the code and the data, but not the three original datasets. The same is true if you download the repository as a
[ZIP file](https://github.com/johentsch/aligned_bach_chorales/archive/refs/heads/main.zip).

### Cloning with original datasets

If you want to be able to re-generate the data, you need to clone the repository recursively, including the original datasets:

    git clone --recurse-submodules https://github.com/johentsch/aligned_bach_chorales.git

Note that for generating the data you need to have the following software installed:

* [humextra](https://github.com/craigsapp/humextra) (for converting **kern to musicxml via `hum2xml`)
* [MuseScore 4](https://musescore.org/en/download) (for converting the datasets to `.mscz` format)
* [ms3](https://pypi.org/project/ms3/) (for doing the batch conversion and extracting notes and measures, included 
  in `requirements.txt`)

If the requirements are filled you can

* head to `craigsapp_krn` and execute `make musicxml` to convert the **kern files to musicxml
* in the top-level directory execute `./extract_data.sh` to convert everything to MuseScore and extract notes and measures.