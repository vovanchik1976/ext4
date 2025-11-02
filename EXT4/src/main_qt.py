import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QAction, QTreeWidget, 
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QSplitter,
    QStatusBar, QPlainTextEdit, QFileDialog, QMessageBox,
    QVBoxLayout, QWidget, QLabel, QInputDialog, QDialog, QListWidget,
    QPushButton, QHBoxLayout
)
from PyQt5.QtCore import Qt
from ext4fs import Ext4FS, Ext4Error

class Ext4GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.fs = Ext4FS()
        self.current_image = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Ext4 Filesystem GUI')
        self.setGeometry(100, 100, 1000, 700)
        
        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Toolbar actions
        self.action_open = QAction('Open Image', self)
        self.action_open.triggered.connect(self.open_image)
        toolbar.addAction(self.action_open)
        
        self.action_format = QAction('Format Image', self)
        self.action_format.triggered.connect(self.format_image)
        toolbar.addAction(self.action_format)
        
        self.action_import = QAction('Import File', self)
        self.action_import.triggered.connect(self.import_file)
        toolbar.addAction(self.action_import)
        
        self.action_new_folder = QAction('New Folder', self)
        self.action_new_folder.triggered.connect(self.new_folder)
        toolbar.addAction(self.action_new_folder)
        
        self.action_rename = QAction('Rename', self)
        self.action_rename.triggered.connect(self.rename_item)
        toolbar.addAction(self.action_rename)
        
        self.action_delete = QAction('Delete', self)
        self.action_delete.triggered.connect(self.delete_item)
        toolbar.addAction(self.action_delete)
        
        self.action_export = QAction('Export', self)
        self.action_export.triggered.connect(self.export_file)
        toolbar.addAction(self.action_export)
        
        self.action_props = QAction('Properties', self)
        self.action_props.triggered.connect(self.show_properties)
        toolbar.addAction(self.action_props)
        
        # Create central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - directory tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel('Directory Tree')
        self.tree_widget.itemClicked.connect(self.on_item_selected)
        self.tree_widget.itemExpanded.connect(self.on_item_expanded)
        splitter.addWidget(self.tree_widget)
        
        # Right panel - properties
        self.props_table = QTableWidget()
        self.props_table.setColumnCount(2)
        self.props_table.setHorizontalHeaderLabels(['Property', 'Value'])
        splitter.addWidget(self.props_table)
        
        # Log panel at bottom
        self.log_panel = QPlainTextEdit()
        self.log_panel.setMaximumHeight(150)
        self.log_panel.setReadOnly(True)
        layout.addWidget(QLabel('Log:'))
        layout.addWidget(self.log_panel)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready')
        
    def log_message(self, message):
        self.log_panel.appendPlainText(message)
        
    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Ext4 Image', '', 'Ext4 Images (*.img *.ext4);;All Files (*)'
        )
        
        if file_path:
            try:
                self.fs.open(file_path, rw=True)
                self.current_image = file_path
                self.status_bar.showMessage(f'Opened: {file_path}')
                self.log_message(f'Opened image: {file_path}')
                self.refresh_tree()
            except Ext4Error as e:
                QMessageBox.critical(self, 'Error', f'Failed to open image: {str(e)}')
                self.log_message(f'Error opening image: {str(e)}')
                
    def format_image(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Create Ext4 Image', '', 'Ext4 Images (*.img *.ext4)'
        )
        
        if file_path:
            try:
                # Default to 64MB image
                self.fs.mkfs(file_path, 64 * 1024 * 1024)
                self.log_message(f'Created new ext4 image: {file_path}')
                QMessageBox.information(self, 'Success', 'Image created successfully')
            except Ext4Error as e:
                QMessageBox.critical(self, 'Error', f'Failed to create image: {str(e)}')
                self.log_message(f'Error creating image: {str(e)}')
                
    def refresh_tree(self):
        self.tree_widget.clear()
        if self.current_image:
            try:
                # Add root item
                root_item = QTreeWidgetItem(['/'])
                root_item.setData(0, Qt.UserRole, '/')
                self.tree_widget.addTopLevelItem(root_item)
                # Add placeholder so it can be expanded
                placeholder = QTreeWidgetItem(['Loading...'])
                root_item.addChild(placeholder)
            except Ext4Error as e:
                self.log_message(f'Error refreshing tree: {str(e)}')
                
    def on_item_expanded(self, item):
        # Remove placeholder children
        while item.childCount() > 0:
            item.removeChild(item.child(0))
            
        path = item.data(0, Qt.UserRole)
        if path:
            self.populate_tree(item, path)
                
    def populate_tree(self, parent_item, path):
        try:
            items = self.fs.listdir(path)
            for item in items:
                if item['name'] not in ['.', '..']:
                    full_path = os.path.join(path, item['name']).replace('\\', '/')
                    tree_item = QTreeWidgetItem([item['name']])
                    tree_item.setData(0, Qt.UserRole, full_path)
                    parent_item.addChild(tree_item)
                    
                    # If it's a directory, add a placeholder child so it can be expanded
                    if item['type'] == 'dir':
                        placeholder = QTreeWidgetItem(['Loading...'])
                        tree_item.addChild(placeholder)
        except Ext4Error as e:
            self.log_message(f'Error populating tree for {path}: {str(e)}')
            
    def on_item_selected(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path:
            try:
                stats = self.fs.stat(path)
                self.props_table.setRowCount(len(stats))
                for row, (key, value) in enumerate(stats.items()):
                    self.props_table.setItem(row, 0, QTableWidgetItem(str(key)))
                    self.props_table.setItem(row, 1, QTableWidgetItem(str(value)))
            except Ext4Error as e:
                self.log_message(f'Error getting properties for {path}: {str(e)}')
                
    def import_file(self):
        if not self.current_image:
            QMessageBox.warning(self, 'Warning', 'Please open an image first')
            return
            
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 'Select files to import', '', 'All Files (*)'
        )
        
        if file_paths:
            # Get current selected directory or use root
            current_item = self.tree_widget.currentItem()
            target_dir = "/"
            if current_item:
                item_path = current_item.data(0, Qt.UserRole)
                if item_path:
                    try:
                        stats = self.fs.stat(item_path)
                        if stats.get('type') == 'dir':
                            target_dir = item_path
                    except Ext4Error:
                        pass
            
            for file_path in file_paths:
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        
                    # Get filename from path
                    filename = os.path.basename(file_path)
                    target_path = os.path.join(target_dir, filename).replace('\\', '/')
                    
                    self.fs.write_overwrite(target_path, data)
                    self.log_message(f'Imported: {filename} to {target_dir}')
                    
                except Exception as e:
                    QMessageBox.critical(self, 'Error', f'Failed to import {file_path}: {str(e)}')
                    self.log_message(f'Error importing {file_path}: {str(e)}')
                    
            self.refresh_tree()
            
    def new_folder(self):
        if not self.current_image:
            QMessageBox.warning(self, 'Warning', 'Please open an image first')
            return
            
        # Get current selected directory or use root
        current_item = self.tree_widget.currentItem()
        parent_dir = "/"
        parent_item = self.tree_widget.topLevelItem(0)  # Root item
        
        if current_item:
            item_path = current_item.data(0, Qt.UserRole)
            if item_path:
                try:
                    stats = self.fs.stat(item_path)
                    if stats.get('type') == 'dir':
                        parent_dir = item_path
                        parent_item = current_item
                except Ext4Error:
                    pass
        
        # Ask for folder name
        folder_name, ok = QInputDialog.getText(self, 'New Folder', 'Folder name:')
        if ok and folder_name:
            try:
                # Create full path
                new_path = os.path.join(parent_dir, folder_name).replace('\\', '/')
                self.fs.mkdirs(new_path, 0o755)
                self.log_message(f'Created directory: {new_path}')
                
                # Update tree
                if parent_item:
                    # Remove placeholder if it exists
                    while parent_item.childCount() > 0 and parent_item.child(0).text(0) == 'Loading...':
                        parent_item.removeChild(parent_item.child(0))
                    
                    # Add new folder to tree
                    new_item = QTreeWidgetItem([folder_name])
                    new_item.setData(0, Qt.UserRole, new_path)
                    parent_item.addChild(new_item)
                    # Add placeholder so it can be expanded
                    placeholder = QTreeWidgetItem(['Loading...'])
                    new_item.addChild(placeholder)
                    
            except Ext4Error as e:
                QMessageBox.critical(self, 'Error', f'Failed to create directory: {str(e)}')
                self.log_message(f'Error creating directory {new_path}: {str(e)}')
                
    def rename_item(self):
        if not self.current_image:
            QMessageBox.warning(self, 'Warning', 'Please open an image first')
            return
            
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'Warning', 'Please select an item to rename')
            return
            
        item_path = current_item.data(0, Qt.UserRole)
        if not item_path:
            return
            
        # Get current name (basename)
        current_name = os.path.basename(item_path)
        
        # Ask for new name
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New name:', text=current_name)
        if ok and new_name and new_name != current_name:
            try:
                self.fs.rename(item_path, new_name)
                self.log_message(f'Renamed: {item_path} to {new_name}')
                
                # Update tree
                current_item.setText(0, new_name)
                # Update the stored path
                dir_name = os.path.dirname(item_path)
                if dir_name:
                    new_path = os.path.join(dir_name, new_name).replace('\\', '/')
                else:
                    new_path = '/' + new_name
                current_item.setData(0, Qt.UserRole, new_path)
                
            except Ext4Error as e:
                QMessageBox.critical(self, 'Error', f'Failed to rename item: {str(e)}')
                self.log_message(f'Error renaming {item_path}: {str(e)}')
                
    def delete_item(self):
        if not self.current_image:
            QMessageBox.warning(self, 'Warning', 'Please open an image first')
            return
            
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'Warning', 'Please select an item to delete')
            return
            
        item_path = current_item.data(0, Qt.UserRole)
        if not item_path:
            return
            
        # Confirm deletion
        reply = QMessageBox.question(self, 'Confirm Delete', 
                                   f'Are you sure you want to delete {item_path}?',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.fs.remove(item_path)
                self.log_message(f'Deleted: {item_path}')
                
                # Update tree
                parent = current_item.parent()
                if parent:
                    parent.removeChild(current_item)
                else:
                    # Removing root item - refresh tree
                    self.refresh_tree()
                    
            except Ext4Error as e:
                QMessageBox.critical(self, 'Error', f'Failed to delete item: {str(e)}')
                self.log_message(f'Error deleting {item_path}: {str(e)}')
                
    def export_file(self):
        if not self.current_image:
            QMessageBox.warning(self, 'Warning', 'Please open an image first')
            return
            
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'Warning', 'Please select a file to export')
            return
            
        item_path = current_item.data(0, Qt.UserRole)
        if not item_path:
            return
            
        try:
            stats = self.fs.stat(item_path)
            if stats.get('type') != 'file':
                QMessageBox.warning(self, 'Warning', 'Only files can be exported')
                return
                
            # Ask for export location
            filename = os.path.basename(item_path)
            export_path, _ = QFileDialog.getSaveFileName(
                self, 'Export File', filename, 'All Files (*)'
            )
            
            if export_path:
                # Read file data
                # Note: This is a simplified approach. For large files, a different approach would be needed
                data = self.fs.read(item_path)
                
                # Write to disk
                with open(export_path, 'wb') as f:
                    f.write(data)
                    
                self.log_message(f'Exported: {item_path} to {export_path}')
                QMessageBox.information(self, 'Success', 'File exported successfully')
                
        except Ext4Error as e:
            QMessageBox.critical(self, 'Error', f'Failed to export file: {str(e)}')
            self.log_message(f'Error exporting {item_path}: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save file: {str(e)}')
            self.log_message(f'Error saving exported file: {str(e)}')
            
    def show_properties(self):
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'Warning', 'Please select an item')
            return
            
        item_path = current_item.data(0, Qt.UserRole)
        if not item_path:
            return
            
        try:
            stats = self.fs.stat(item_path)
            
            # Create properties dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f'Properties: {os.path.basename(item_path)}')
            dialog.setGeometry(200, 200, 400, 300)
            
            layout = QVBoxLayout()
            
            # Properties list
            prop_list = QListWidget()
            for key, value in stats.items():
                prop_list.addItem(f'{key}: {value}')
                
            layout.addWidget(prop_list)
            
            # Close button
            close_btn = QPushButton('Close')
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except Ext4Error as e:
            QMessageBox.critical(self, 'Error', f'Failed to get properties: {str(e)}')
            self.log_message(f'Error getting properties for {item_path}: {str(e)}')

def main():
    app = QApplication(sys.argv)
    window = Ext4GUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

