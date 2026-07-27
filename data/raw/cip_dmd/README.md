# Center for industrial Productivity Discrete Manufacturing Dataset (CiP-DMD)
This README contains further information on the structure of the CiP-DMD dataset that 
was published as part of the following article:

```
@article{TBD,
  title={A new benchmark dataset for machine learning applications in discrete
manufacturing: CiP-DMD},
  author={Jourdan, Nicolas and Biegel, Tobias and Cassoli, Beatriz Bretones and Metternich, Joachim},
  journal={Procedia CIRP},
  volume={TBD},
  pages={TBD},
  year={TBD},
  publisher={Elsevier}
}
```
The article contains further information about the experiment setting and the manufacturing process.
Please cite the article accordingly if you intend to use this dataset for an academic publication.

## Disclaimer

The latest update of the dataset contains the following number of produced parts/products:

1. 928 piston rods
2. 847 cylinder bottoms
3. 802 assembled cylinders

## Dataset Structure
The files of the dataset are structured as follows:
```
|
├── README.MD
├── cylinder
│   ├── assembly
│   │   └── quality_data
│   │       └── quality_data.csv
│   └── meta_data.json
├── cylinder_bottom
│   ├── cnc_milling_machine
│   │   ├── process_data
│   │   │   ├── 100101_11_29_2022_12_30_29
│   │   │   │   ├── backside_external_sensor_signals.h5
│   │   │   │   ├── backside_internal_machine_signals.h5
│   │   │   │   ├── backside_timestamp_process_pairs.csv
│   │   │   │   ├── frontside_external_sensor_signals.h5
│   │   │   │   ├── frontside_internal_machine_signals.h5
│   │   │   │   └── frontside_timestamp_process_pairs.csv
│   │   │   ├── ...
│   │   │   │
│   │   └── quality_data
│   │       └── quality_data.csv
│   ├── meta_data.json
│   └── saw
│       ├── process_data
│       │   ├── 100101_8_16_2022_7_59_47
│       │   │   └── internal_machine_signals.h5
│       │   ├── ...
│       │   │
│       └── quality_data
│           └── quality_data.csv
└── piston_rod
    ├── cnc_lathe
    │   ├── process_data
    │   │   ├── 200201_9_6_2022_11_33_24
    │   │   │   └── internal_machine_signals.h5
    │   │   ├── ...
    │   │   │	    
    │   └── quality_data
    │       └── quality_data.csv
    ├── meta_data.json
    └── meta_data_unassembled.json
```

- **Components**:
    - *piston_rod* - machined by CNC lathe
    - *cylinder bottom* - cut by saw and then machined by CNC milling machine
    - *cylinder* -  contain a piston rod and a cylinder bottom each as subparts
- **Machine**:
    - CNC lathe (Index C65)
    - Saw (Kasto SBA 2)
    - CNC milling machine (DMC 50H)

### Data formatting
Two major file formats exist that store the different kinds of data included in the dataset:

- **HDF5 (.h5)**: Stores multivariate time series process data
- **JSON (.json)**: Stores meta data with information about the process and quality control

### Process data

All process data is stored in single hdf5 datasets with key *data*. Column names can be accessed by calling *.attrs["column_names"]* on the dataset:

	with h5py.File('internal_machine_signals.h5', 'r') as hf:
		data = hf["data"]
		column_names = hf['data'].attrs["column_names"]

The processes `cylinder_bottom-saw` as well as `piston_rod-cnc_lathe` have internal PLC data for the complete process stored in `internal_machine_signals.h5` as shown above. The process `cylinder_bottom-cnc_milling_machine` has internal PLC data `internal_machine_signals.h5` as
well as external accelerometer data `external_sensor_signals.h5`. Both are additionally divided into part faces `frontside_*.h5 / backside_*.h5` and subprocesses.
The subprocesses for the part faces can be identified by their timestamps as given in the files `*_timestamp_process_pairs.csv` files, e.g.:

    1669723074,face_milling
    1669723126,circular_pocket_milling
    1669723155,component_deburring
    1669723181,ring_groove

The timestamp indicates the start time of the respective subprocess. Note that some folders in `cylinder_bottom-cnc_milling_machine` contain additional .h5 files that contain the signals of Pro-Micron spike sensory tool
holders 

### Meta data

All meta data is stored in JSON files that contain all data for a component `piston rod/ cylinder_bottom / cylinder` in a single file. The files are all structured identically, e.g.:

    {
        "part_type": "piston_rod",
        "part_id": "200203",
        "component_ids": [],
        "process_data": [
            {
                "data_paths": [
                    "piston_rod/cnc_lathe/process_data/200203_9_6_2022_11_36_14/internal_machine_signals.h5"
                ],
                "start_time": 1662456974.095936,
                "end_time": 1662457069.903286,
                "name": "cnc_lathe",
                "anomaly": 0
            }
        ],
        "quality_data": [
            {
                "process": "cnc_lathe",
                "measurements": [
                    {
                        "feature": "coaxiality",
                        "value": "44.4",
                        "qc_pass": true
                    },
                    {
                        "feature": "diameter",
                        "value": "0.0055",
                        "qc_pass": true
                    },
                    {
                        "feature": "length",
                        "value": "163.652",
                        "qc_pass": true
                    }
                ]
            }
        ]
    },

Please not that, for the piston rods, there are two meta data files. The file `meta_data_unassembled.json` contains additional piston rods (INSERT NUMBER HERE), 
that have been manufactured, but could not be assembled due to uneven edges that may have resulted from excessive wear of the cutting tools. These may be used for 
an additional anomaly detection task.

## Anomaly classes

Two of the most common errors causing faulty cylinder bottoms in our process have been intentionally provoked during data collection. Anomaly classes are stored in the meta data of a component.

- **0** : Normal process
- **1** : Raw cutting material was badly aligned at the saw
    - Anomalous sawing process (raw cylinder bottom cut too short)
    - Anomalous milling proces
- **2** : Part was unevenly clamped in the milling jig
    - Anomalous milling process
- **3** : Miscellaneous errors happened during the process that are not visible in process data

## Quality control limits

The following quality control limits are used to determine the `qc_pass` value in the meta data files:

| Process      | Part            | Measurement       | Lower bound | Upper bound |
|--------------|-----------------|-------------------|-------------|-------------|
| **Lathing**  | Piston rod      | Coaxiality        | 0           | 50          |
| ""           | ""              | Diameter          | -0.018      | 0.018       |
| ""           | ""              | Length            | 163.45      | 163.75      |
| **Sawing**   | Cylinder bottom | Weight            | 0.495       | 0.641       |
| **Milling**  | Cylinder bottom | Groove depth      | 0.75        | 0.85        |
| ""           | ""              | Groove diameter   | 39.906      | 39.999      |
| ""           | ""              | Parallelism       | 0           | 0.1         |
| ""           | ""              | Surface Roughness | 0           | 2.5         |
| **Assembly** | Cylinder        | Pressure          | 7564.452    | 16486.026   |
