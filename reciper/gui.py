#!/usr/bin/env python

# Calour GUI - a full GUI wrapping for calour functions

# ----------------------------------------------------------------------------
# Copyright (c) 2016--,  Calour development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import sys
from logging import getLogger, basicConfig
import logging
import argparse

from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout,
                             QWidget, QPushButton, QLabel,
                             QComboBox, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox,
                             QDialog, QDialogButtonBox, QApplication, QListWidget)
import matplotlib
import numpy as np
from scipy.optimize import linprog
from fatsecret import Fatsecret


# we need this because of the skbio import that probably imports pyplot?
# must have it before importing calour (Since it imports skbio)
matplotlib.use("Qt5Agg")

__version__ = 0.1

logger = getLogger(__name__)
# set the logger output according to log.cfg
basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class AppWindow(QtWidgets.QMainWindow):
    def __init__(self):
        '''Start the gui
        '''
        super().__init__()
        self.ingredients = []
        self.values = {}
        ck = 'b06a262d0e0b4321981d8c15d2cb866b'
        cs = 'bf6c1708b7ec4fedb7c3d0381ea7a2db'
        fs = Fatsecret(ck, cs)
        self.fs = fs

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        main_widget = QWidget(self)
        layout = QVBoxLayout(main_widget)

        button = QPushButton('Values')
        button.clicked.connect(self.get_values)
        layout.addWidget(button)

        self.w_search_ingredient = QLineEdit('pita')
        self.w_search_ingredient.returnPressed.connect(self.search)

        button = QPushButton('RecipeIt')
        button.clicked.connect(self.get_recipe)
        layout.addWidget(button)

        layout.addWidget(self.w_search_ingredient)
        # hlayout.addWidget(search_ingredient)

        self.w_ingredient_list = QListWidget()
        layout.addWidget(self.w_ingredient_list)

        self.ingredients = {}

        self.setWindowTitle('Reciper version %s' % __version__)
        main_widget.setFocus()
        self.setCentralWidget(main_widget)
        self.show()

    def search(self):
        logger.debug('search')
        ingredient = self.w_search_ingredient.text()
        logger.debug('searching for term %s' % ingredient)
        if ingredient in self.ingredients:
            pass
        foods = self.fs.foods_search(ingredient)
        fooddata = {}
        for cfood in foods:
            if 'food_name' in cfood:
                if 'food_id' in cfood:
                    fooddata[cfood['food_name']] = cfood['food_id']
                # print(cfood['food_name'])
                # print(cfood['food_id'])
        slist = SListWindow(listdata=list(fooddata.keys()))
        slist.exec_()
        res = slist.w_list.selectedItems()
        selected_food = res[0].text()
        selected_id = fooddata[selected_food]
        res = self.fs.food_get(selected_id)
        logger.debug(res)
        if 'servings' not in res:
            logger.warning('servings not in res')
            return
        serving = res['servings']
        serving = serving['serving']
        if isinstance(serving, list):
            # serving = self.select_serving(serving)
            serving = serving[0]

        # show the info about the ingredient
        info = []
        info.append(selected_food)
        info.append('measurement unit: %s' % serving.get('measurement_description'))
        for ck, cv in serving.items():
            info.append('%s: %s' % (ck, cv))
        info_list = SListWindow(info)
        res = info_list.exec_()
        print(res)
        self.ingredients[selected_food] = serving
        self.w_ingredient_list.addItem(selected_food)

    def select_serving(self, servings):
        for cserving in servings:
            if 'metric_serving_unit' not in cserving:
                logger.info('metric_serving_unit not found in %s. skipping' % cserving)
                continue
            if cserving['metric_serving_unit'] != 'g':
                logger.info('found serving unit %s. skipping' % cserving['metric_serving_unit'])
                continue
            if 'metric_serving_amount' not in cserving:
                print('metric_serving_amount not in cserving')
                print(cserving)
                return
            # print(cserving['metric_serving_amount'])
            print(float(cserving['calories']) / float(cserving['metric_serving_amount']))

    def get_values(self, widget):
        logger.debug('values')
        keys = []
        params = ['calories', 'carbohydrate', 'fat', 'fiber', 'sodium', 'protein', 'sugar']
        for ckey in params:
            cdict = {'type': 'string', 'label': ckey, 'default': str(self.values.get(ckey, 0))}
            keys.append(cdict)
            cdict = {'type': 'bool', 'label': 'use_%s' % ckey, 'default': True}
            keys.append(cdict)
        # for ckey in ['calcium', 'cholesterol', 'iron', 'monounsaturated_fat', 'polyunsaturated_fat', 'saturated_fat', 'potassium', 'trans_fat', 'vitamin_a', 'vitamin_c']:
        #     cdict = {'type': 'string', 'label': ckey}
        #     keys.append(cdict)
        #     cdict = {'type': 'bool', 'label': 'use_%s' % ckey, 'default': False}
        #     keys.append(cdict)

        res = dialog(keys, expdat=None)
        if res is None:
            return
        self.values = {}
        for ckey in params:
            if res['use_%s' % ckey]:
                self.values[ckey] = float(res[ckey])
        logger.info('obtained %d new values' % len(self.values))
        logger.debug(self.values)

    def get_recipe(self):
        logger.debug('recipe for %d values using %d ingredients' % (len(self.values), len(self.ingredients)))

        # we have the variables:
        # one per ingredient
        # one per remainder parameter (normalized to 1)
        # and we minimize the remaineder parameters

        eq_coeff = []
        eq_const = []
        # ineq_coeff = []
        # ineq_const = []
        # # create the positivity inequalities (all ingredients >= 0)
        # for idx, cingredient in enumerate(self.ingredients.values()):
        #     cc = np.zeros(len(self.ingredients) + len(self.parameters))
        #     cc[idx] = 1
        #     ineq_coeff.append(cc)
        #     ineq_const.append(0)

        # main equations (per calories/protein/etc.)
        for idx2, (cparam, cval) in enumerate(self.values.items()):
            cc = np.zeros(len(self.ingredients) + len(self.values))
            for idx, (cname, cingredient) in enumerate(self.ingredients.items()):
                if cparam not in cingredient:
                    logger.warning('parameter %s not in ingredient %s' % (cparam, cname))
                    continue
                cc[idx] = cingredient[cparam]
            # the free parameter for each parameters, to get the error
            cc[len(self.ingredients) + idx2] = 1
            eq_coeff.append(cc)
            eq_const.append(cval)
        # order limits (ingredient1 >= ingredient2 >= ...)
        # need units of igredients to be correct

        # and the minimize function - sum of the per parameter errors
        err_eq = np.zeros(len(self.ingredients) + len(self.values))
        for idx, cval in enumerate(self.values.values()):
            err_eq[len(self.ingredients) + idx] = 1 / (cval + 0.0000001)

        # and solve
        res = linprog(err_eq, A_eq=eq_coeff, b_eq=eq_const)
        logger.debug(res)
        for idx, cingredient in enumerate(self.ingredients.keys()):
            print('ingredient %s (%s) - amount %f' % (cingredient, self.ingredients[cingredient].get('measurement_description', 'NA'), res.x[idx]))
        for idx, cparam in enumerate(self.values.keys()):
            print('parameter %s error %f' % (cparam, res.x[idx + len(self.ingredients)]))


def dialog(items, expdat=None, title=None):
    '''Create a dialog with the given items for then experiment

    Parameters
    ----------
    items : list of dict
        Entry for each item to display. fields in the dict are:
            'type' :
                'string' : a string (single line)
                'field' : a field from the sample_metadata
                'value' : a value input for the field in the field item
                'bool' : a boolean
                'label' : a label to display (text in 'label' field)
            'default' : the value to initialize the item to
            'label' : str
                label of the item (also the name in the output dict)
    expdat : Experiment (optional)
        the experiment to use to get the field/values items (needed if item is 'field'/'value')
    title : str (optional)
        title of the dialog

    Returns
    -------
    output : dict or None
        if cancel was selected, return None
        otherwise, a dict with label as key, value as val
    '''
    class DialogWindow(QDialog):
        def __init__(self, items, title=None, expdat=None):
            super().__init__()
            self.additional_info = {}
            self._expdat = expdat
            if title:
                self.setWindowTitle(title)

            self.main_widget = QWidget(self)
            self.layout = QVBoxLayout(self)

            self.widgets = {}
            for idx, citem in enumerate(items):
                if citem['type'] == 'label':
                    widget = QLabel(text=citem.get('label'))
                    self.add(widget)
                elif citem['type'] == 'string':
                    widget = QLineEdit(citem.get('default'))
                    self.add(widget, label=citem.get('label'), name=citem.get('label'))
                elif citem['type'] == 'int':
                    widget = QSpinBox()
                    if 'max' in citem:
                        widget.setMaximum(citem['max'])
                    if 'default' in citem:
                        widget.setValue(citem.get('default'))
                    self.add(widget, label=citem.get('label'), name=citem.get('label'))
                elif citem['type'] == 'float':
                    widget = QDoubleSpinBox()
                    if 'max' in citem:
                        widget.setMaximum(citem['max'])
                    if 'default' in citem:
                        widget.setValue(citem.get('default'))
                    self.add(widget, label=citem.get('label'), name=citem.get('label'))
                elif citem['type'] == 'combo':
                    widget = QComboBox()
                    widget.addItems(citem.get('items'))
                    self.add(widget, label=citem.get('label'), name=citem.get('label'))
                elif citem['type'] == 'field':
                    if expdat is None:
                        logger.warn('Experiment is empty for dialog %s' % title)
                        return None
                    widget = QComboBox()
                    if citem.get('withnone', False):
                        items = ['<none>'] + list(expdat.sample_metadata.columns.values)
                    else:
                        items = expdat.sample_metadata.columns.values
                    widget.addItems(items)
                    self.add(widget, label=citem.get('label'), name='field')
                elif citem['type'] == 'value':
                    if expdat is None:
                        logger.warn('Experiment is empty for dialog %s' % title)
                        return None
                    widget = QLineEdit()
                    self.add(widget, label=citem.get('label'), name=citem.get('label'), addbutton=True)
                elif citem['type'] == 'value_multi_select':
                    if expdat is None:
                        logger.warn('Experiment is empty for dialog %s' % title)
                        return None
                    widget = QLineEdit()
                    self.add(widget, label=citem.get('label'), name=citem.get('label'), add_select_button=citem, idx=idx)
                elif citem['type'] == 'filename':
                    widget = QLineEdit()
                    self.add(widget, label=citem.get('label'), name=citem.get('label'), addfilebutton=True)
                elif citem['type'] == 'bool':
                    widget = QCheckBox()
                    if 'default' in citem:
                        widget.setChecked(citem.get('default'))
                    self.add(widget, label=citem.get('label'), name=citem.get('label'))
                elif citem['type'] == 'select':
                    widget = QLabel('<None>')
                    citem['selected'] = []
                    self.add(widget, label=citem.get('label'), name=citem.get('label'), add_select_button=citem, idx=idx)

            buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

            buttonBox.accepted.connect(self.accept)
            buttonBox.rejected.connect(self.reject)

            self.layout.addWidget(buttonBox)

        def add(self, widget, name=None, label=None, addbutton=False, addfilebutton=False, add_select_button=None, idx=None):
            '''Add the widget to the dialog

            Parameters
            ----------
            widget
            name: str or None, optional
                the name of the data field for obtaining the value when ok clicked
            label: str or None, optional
                The label to add to the widget (to display in the dialog)
            addbutton: bool, optional
                True to add a button which opens the selection from field dialog
            addfilebutton: bool, optional
                True to add a file select dialog button
            add_select_button: item or None, optional
                not None to add a button opening a multi select dialog for values from the 'items' field. If 'items' field is None, select from current 'field' values
            '''
            hlayout = QHBoxLayout()
            if label is not None:
                label_widget = QLabel(label)
                hlayout.addWidget(label_widget)
            hlayout.addWidget(widget)
            if addbutton:
                bwidget = QPushButton(text='...')
                bwidget.clicked.connect(lambda: self.field_vals_click(widget))
                hlayout.addWidget(bwidget)
            if addfilebutton:
                bwidget = QPushButton(text='...')
                bwidget.clicked.connect(lambda: self.file_button_click(widget))
                hlayout.addWidget(bwidget)
            if add_select_button is not None:
                bwidget = QPushButton(text='...', parent=widget)
                bwidget.clicked.connect(lambda: self.select_items_click(widget, add_select_button))
                hlayout.addWidget(bwidget)
            self.layout.addLayout(hlayout)
            self.widgets[name] = widget

        def field_vals_click(self, widget):
            cfield = str(self.widgets['field'].currentText())
            if cfield not in self._expdat.sample_metadata.columns:
                return
            val, ok = QtWidgets.QInputDialog.getItem(self, 'Select value', 'Field=%s' % cfield, list(set(self._expdat.sample_metadata[cfield].astype(str))))
            if ok:
                widget.setText(val)

        def file_button_click(self, widget):
            fname, _x = QtWidgets.QFileDialog.getOpenFileName(self, 'Open fasta file')
            fname = str(fname)
            if fname != '':
                widget.setText(fname)

        def select_items_click(self, widget, item):
            select_items = item.get('items')

            # set the values according to the field if it is a field multi-select
            if select_items is None:
                cfield = str(self.widgets['field'].currentText())
                select_items = list(set(self._expdat.sample_metadata[cfield].astype(str)))

            selected = select_list_items(select_items)
            # set the selected list text in the text widget
            if len(selected) == 0:
                selected_str = '<None>'
            else:
                selected_str = ','.join(selected)
            widget.setText(selected_str)
            item['selected'] = selected

        def get_output(self, items):
            output = {}
            for citem in items:
                cname = citem.get('label')
                if citem['type'] == 'string':
                    output[cname] = str(self.widgets[cname].text())
                if citem['type'] == 'int':
                    output[cname] = self.widgets[cname].value()
                if citem['type'] == 'float':
                    output[cname] = self.widgets[cname].value()
                elif citem['type'] == 'combo':
                    output[cname] = str(self.widgets[cname].currentText())
                elif citem['type'] == 'field':
                    output['field'] = str(self.widgets['field'].currentText())
                    if output['field'] == '<none>':
                        output['field'] = None
                elif citem['type'] == 'value':
                    cval = str(self.widgets[cname].text())
                    if str(self.widgets['field'].currentText()) != '<none>':
                        # convert the value from str to the field dtype
                        cval = _value_to_dtype(cval, self._expdat, self.widgets['field'].currentText())
                    output[cname] = cval
                elif citem['type'] == 'filename':
                    output[cname] = str(self.widgets[cname].text())
                elif citem['type'] == 'bool':
                    output[cname] = self.widgets[cname].checkState() > 0
                elif citem['type'] == 'select':
                    output[cname] = citem['selected']
                elif citem['type'] == 'value_multi_select':
                    output[cname] = citem['selected']
            return output

    aw = DialogWindow(items, expdat=expdat)
    aw.show()
    # if app_created:
    #     app.references.add(self.aw)
    aw.adjustSize()
    res = aw.exec_()
    # if cancel pressed - return None
    if not res:
        return None
    output = aw.get_output(items)
    return output


class SelectListWindow(QtWidgets.QDialog):
    def __init__(self, all_items):
        super().__init__()
        uic.loadUi(get_ui_file_name('list_select.ui'), self)
        self.wAdd.clicked.connect(self.add)
        self.wRemove.clicked.connect(self.remove)

        for citem in all_items:
            self.wListAll.addItem(citem)

    def add(self):
        items = self.wListAll.selectedItems()
        for citem in items:
            cname = str(citem.text())
            self.wListSelected.addItem(cname)
            self.wListAll.takeItem(self.wListAll.row(citem))

    def remove(self):
        items = self.wListSelected.selectedItems()
        for citem in items:
            cname = str(citem.text())
            self.wListAll.addItem(cname)
            self.wListSelected.takeItem(self.wListSelected.row(citem))


def select_list_items(all_items):
        win = SelectListWindow(all_items)
        res = win.exec_()
        if res == QtWidgets.QDialog.Accepted:
            selected = [str(win.wListSelected.item(i).text()) for i in range(win.wListSelected.count())]
            return selected
        else:
            return []


class SListWindow(QtWidgets.QDialog):
    def __init__(self, listdata=[], listname=None):
        '''Create a list window with items in the list and the listname as specified

        Parameters
        ----------
        listdata: list of str, optional
            the data to show in the list
        listname: str, optional
            name to display above the list
        '''
        super().__init__()
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        if listname is not None:
            self.setWindowTitle(listname)

        self.layout = QVBoxLayout(self)

        self.w_list = QListWidget()
        self.layout.addWidget(self.w_list)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        self.layout.addWidget(buttonBox)

        for citem in listdata:
            self.w_list.addItem(citem)

        self.show()
        self.adjustSize()


def init_qt5():
    '''Init the qt5 event loop

    Parameters
    ----------

    Returns
    -------
    app :
        QCoreApplication
    app_created : bool
        True if a new QApplication was created, False if using existing one
    '''
    app_created = False
    app = QtCore.QCoreApplication.instance()
    if app is None:
        # app = QApplication(sys.argv)
        app = QApplication(sys.argv)
        app_created = True
        logger.debug('Qt app created')
    logger.debug('Qt app is %s' % app)
    if not hasattr(app, 'references'):
        app.references = set()

    return app, app_created


def _value_to_dtype(val, exp, field):
    '''Get the value converted to the field dtype

    Parameters
    ----------
    val : str
        the value to convet from
    exp : Experiment
        containing the field
    field : str
        name of the field in experiment sample metadata to take the new type from

    Returns
    any_type
        the value converted to the exp/field data type
    '''
    svalue = np.array([val])
    svalue = svalue.astype(exp.sample_metadata[field].dtype)
    svalue = svalue[0]
    return svalue


def main():
    parser = argparse.ArgumentParser(description='GUI for Calour microbiome analysis')
    parser.add_argument('--log-level', help='debug log level', default=20, type=int)

    args = parser.parse_args()

    logger.setLevel(args.log_level)

    logger.info('starting reciper version %s' % __version__)
    # app = QtWidgets.QApplication(sys.argv)
    app, app_created = init_qt5()
    window = AppWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
