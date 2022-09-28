import configparser
import glob
import os

from qtpy.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)
import pandas as pd
import tifffile


class KoopaWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()

        # General config
        self.viewer = napari_viewer
        self.spots_cols = ["frame", "y", "x"]
        self.track_cols = ["particle", "frame", "y", "x"]

        # Build plugin layout
        self.setLayout(QVBoxLayout())
        self.setup_config_parser()
        self.layout().addWidget(self.get_separator_line())
        self.setup_file_dropdown()
        self.layout().addWidget(self.get_separator_line())
        self.setup_save_widget()
        self.layout().addWidget(self.get_separator_line())
        self.setup_file_navigation()
        self.layout().addWidget(self.get_separator_line())
        self.setup_progress_bar()

    def get_separator_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def setup_config_parser(self):
        """Prepare widget for config reader."""
        widget = QWidget()
        widget.setLayout(QVBoxLayout())
        widget.layout().addWidget(QLabel("Analysis Directory"))

        btn_widget = QPushButton("Select")
        btn_widget.clicked.connect(self.open_file_dialog)
        widget.layout().addWidget(btn_widget)
        self.layout().addWidget(widget)

    def setup_file_dropdown(self):
        widget = QWidget()
        widget.setLayout(QVBoxLayout())
        widget.layout().addWidget(QLabel("Current File"))

        self.dropdown_widget = QComboBox()
        widget.layout().addWidget(self.dropdown_widget)

        btn_widget = QPushButton("Load")
        btn_widget.clicked.connect(self.load_file)
        widget.layout().addWidget(btn_widget)

        self.file_dropdown = widget
        self.file_dropdown.setDisabled(True)
        self.layout().addWidget(self.file_dropdown)

    def setup_save_widget(self):
        widget = QWidget()
        widget.setLayout(QVBoxLayout())
        widget.layout().addWidget(QLabel("Save Edits"))
        btn_widget = QPushButton("Run")
        btn_widget.clicked.connect(self.save_edits)
        widget.layout().addWidget(btn_widget)

        self.save_widget = widget
        self.save_widget.setDisabled(True)
        self.layout().addWidget(self.save_widget)

    def setup_file_navigation(self):
        widget = QWidget()
        widget.setLayout(QHBoxLayout())
        widget.layout().addWidget(QLabel("Navigate Files"))
        prev_widget = QPushButton("Prev Image")
        prev_widget.clicked.connect(lambda: self.change_file("prev"))
        widget.layout().addWidget(prev_widget)
        next_widget = QPushButton("Next Image")
        next_widget.clicked.connect(lambda: self.change_file("next"))
        widget.layout().addWidget(next_widget)

        self.file_navigation = widget
        self.file_navigation.setDisabled(True)
        self.layout().addWidget(self.file_navigation)

    def setup_progress_bar(self):
        self.pbar = QProgressBar(self)
        self.pbar.setValue(0)
        self.layout().addWidget(self.pbar)

    def open_file_dialog(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)
        if dialog.exec_():
            self.analysis_path = dialog.selectedFiles()[0]
            self.run_config_parser()
            self.get_file_list()

    def run_config_parser(self):
        """Retrieve config file from analysis directory."""
        config_file = os.path.join(
            os.path.abspath(self.analysis_path), "koopa.cfg"
        )
        if not os.path.exists(config_file):
            raise ValueError("Koopa config file does not exist!")

        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def load_file(self):
        """Ope n all associated files and enable editing."""
        self.name = self.dropdown_widget.currentText()

        self.pbar.setValue(0)
        self.load_image()
        self.pbar.setValue(25)
        self.load_segmentation_cells()
        self.pbar.setValue(50)
        if eval(self.config["SegmentationOther"]["enabled"]):
            self.load_segmentation_other()
        self.pbar.setValue(90)
        self.load_segmentation_raw()
        self.pbar.setValue(100)
        if eval(self.config["SpotsColocalization"]["enabled"]):
            self.load_colocalization()
        self.save_widget.setDisabled(False)

    def save_edits(self):
        print("saving shit")

    def change_file(self, option: str):
        print(f"option is {option}")

    def get_file_list(self):
        files = sorted(
            glob.glob(
                os.path.join(self.analysis_path, "preprocessed", "*.tif")
            )
        )
        files = sorted(
            [os.path.basename(f).replace(".tif", "") for f in files]
        )
        self.file_dropdown.setDisabled(False)
        self.file_navigation.setDisabled(False)
        self.dropdown_widget.addItems(files)

    def load_image(self):
        fname = os.path.join(
            self.analysis_path, "preprocessed", f"{self.name}.tif"
        )
        image = tifffile.imread(fname)
        for idx, channel in enumerate(image):
            self.pbar.setValue(25 / len(image) * idx)
            self.viewer.add_image(
                channel, name=f"Channel {idx}", blending="additive"
            )

    def load_segmentation_cells(self):
        fname = os.path.join(
            self.analysis_path, "segmentation_primary", f"{self.name}.tif"
        )
        segmap = tifffile.imread(fname).astype(int)
        self.viewer.add_labels(
            segmap, name="Segmentation Primary", blending="translucent"
        )

    def load_segmentation_other(self):
        for channel in eval(self.config["SegmentationOther"]["channels"]):
            fname = os.path.join(
                self.analysis_path,
                f"segmentation_{channel}",
                f"{self.name}.tif",
            )
            segmap = tifffile.imread(fname).astype(int)
            self.viewer.add_labels(
                segmap, name=f"Segmentation C{channel}", blending="translucent"
            )

    def load_segmentation_raw(self):
        do_timeseries = eval(self.config["General"]["do_TimeSeries"])
        do_3D = eval(self.config["General"]["do_3D"])

        for channel in eval(self.config["SpotsDetection"]["channels"]):
            folder = (
                f"detection_final_c{channel}"
                if do_3D or do_timeseries
                else f"detection_raw_c{channel}"
            )
            fname = os.path.join(
                self.analysis_path, folder, f"{self.name}.parq"
            )
            df = pd.read_parquet(fname)
            if do_timeseries:
                self.viewer.add_tracks(
                    df[self.track_cols], name=f"Track C{channel}"
                )
            else:
                self.viewer.add_points(
                    df[self.spots_cols], name=f"Detection C{channel}"
                )

