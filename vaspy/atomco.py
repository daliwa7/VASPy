# -*- coding:utf-8 -*-
"""
===================================================================
Provide coordinate file class which do operations on these files.
===================================================================
Written by PytLab <shaozhengjiang@gmail.com>, November 2014
Updated by PytLab <shaozhengjiang@gmail.com>, May 2017

==============================================================

"""
import logging
import re
from collections import namedtuple

import numpy as np

from vaspy import VasPy
from vaspy.errors import CarfileValueError
from vaspy.functions import *


class AtomCo(VasPy):
    "Base class to be inherited by atomco classes."
    def __init__(self, filename):
        VasPy.__init__(self, filename)

    def verify(self):
        if len(self.data) != self.natom:
            raise CarfileValueError('Atom numbers mismatch!')

    @property
    def atomco_dict(self):
        """
        Return the current atom type and coordinates mapping, 
        make sure the data in dict can be updated in time.
        """
        return self.get_atomco_dict(self.data)

    @property
    def tf_dict(self):
        """
        Return the current atom type and T/F mapping, make sure the data
        can be updated in time when returned.
        """
        return self.get_tf_dict(self.tf)

    def get_atomco_dict(self, data):
        """
        根据已获取的data和atoms, atoms_num, 获取atomco_dict
        """
        # [1, 1, 1, 16] -> [0, 1, 2, 3, 19]
        idx_list = [sum(self.atom_numbers[:i])
                    for i in range(1, len(self.atom_types)+1)]
        idx_list = [0] + idx_list

        data_list = data.tolist()
        atomco_dict = {}
        for atom_type, idx, next_idx in zip(self.atom_types,
                                            idx_list[:-1],
                                            idx_list[1:]):
            atomco_dict.setdefault(atom_type, data_list[idx: next_idx])

        return atomco_dict

    def get_tf_dict(self, tf):
        """
        根据已获取的tf和atoms, atoms_num, 获取tf_dict
        """
        # [1, 1, 1, 16] -> [0, 1, 2, 3, 19]
        idx_list = [sum(self.atom_numbers[:i])
                    for i in range(1, len(self.atom_types)+1)]
        idx_list = [0] + idx_list

        tf_list = tf.tolist()
        tf_dict = {}
        for atom_type, idx, next_idx in zip(self.atom_types,
                                            idx_list[:-1],
                                            idx_list[1:]):
            tf_dict.setdefault(atom_type, tf_list[idx: next_idx])

        return tf_dict

    def get_xyz_content(self, step=None):

        """
        Get xyz file content.
        获取最新.xyz文件内容字符串

        Parameters:
        -----------
        step: The step number, int, optional, 1 by default.
        """
        natom = "{:12d}\n".format(self.natom)
        try:
            step = self.step if step is None else step
        except AttributeError:
            step = 1
        step = "STEP ={:9d}\n".format(step)
        data = atomdict2str(self.atomco_dict, self.atom_types)
        content = natom + step + data

        return content

    def get_poscar_content(self, **kwargs):
        """
        Get POSCAR content.
        根据对象数据获取poscar文件内容字符串

        Parameters:
        -----------
        bases_const: The constant for basis vectors, optional, 1.0 by default.

        bases: The basis vectors for the lattice, option, 3x3 np.array.
               [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]] by default.

        tf: The T/F info for all atoms. Nx3 np.array, n is the length of 0th axis of data.
        """
        content = 'Created by VASPy\n'

        # bases constant.
        try:
            bases_const = self.bases_const
        except AttributeError:
            bases_const = kwargs.get("bases_const", 1.0)
        bases_const = " {:.9f}\n".format(bases_const)

        # bases
        try:
            bases = self.bases
        except AttributeError:
            bases = kwargs.get("bases", np.array([[1.0, 0.0, 0.0],
                                                  [0.0, 1.0, 0.0],
                                                  [0.0, 0.0, 1.0]]))
        bases_list = bases.tolist()
        bases = ''
        for basis in bases_list:
            bases += "{:14.8f}{:14.8f}{:14.8f}\n".format(*basis)

        # atom info
        types, numbers = self.atom_types, self.atom_numbers
        atom_types = ("{:5s}"*len(types) + "\n").format(*types)
        atom_numbers = ("{:5d}"*len(numbers) + "\n").format(*numbers)

        # string
        info = "Selective Dynamics\nDirect\n"

        # data and tf
        try:
            tf = self.tf
        except AttributeError:
            # Initialize tf with 'T's.
            default_tf = np.full(self.data.shape, 'T', dtype=np.str)
            tf = kwargs.get("tf", default_tf)
        data_tf = ''
        for data, tf in zip(self.data.tolist(), tf.tolist()):
            data_tf += ("{:18.12f}"*3+"{:5s}"*3+"\n").format(*(data+tf))

        # merge all strings
        content += (bases_const + bases + atom_types + atom_numbers +
                    info + data_tf)

        return content

    def get_volume(self):
        """
        Get volume of slab(Angstrom^3)
        获取晶格体积
        """
        if hasattr(self, 'bases_const') and hasattr(self, 'bases'):
            bases = self.bases_const*self.bases
            volume = np.linalg.det(bases)
            self.volume = volume
        else:
            raise AttributeError("Object has no bases and bases_const")

        return volume

    @staticmethod
    def dir2cart(bases, data):
        """
        Static method to convert direct coordinates to Cartisan coordinates.

        Parameters:
        -----------
        bases: The 3x3 array for basis vectors, 3x3 numpy.array.

        data: The direct coordinate data, Nx3 numpy.array.
        """
        A = np.matrix(bases).T
        x = np.matrix(data).T
        b = A*x

        b = np.array(b.T)

        if b.shape[0] == 1:
            b = b.reshape(3, )

        return b

    @staticmethod
    def cart2dir(bases, data):
        """
        Static method to convert Cartisian coordinates to direct coordinates.

        Parameters:
        -----------
        bases: The 3x3 array for basis vectors, 3x3 numpy.array.

        data: The Cartisan coordinate data, Nx3 numpy.array or a single 3D vector.
        """
        b = np.matrix(data).T
        A = np.matrix(bases).T
        x = A.I*b

        x = np.array(x.T)
        if x.shape[0] == 1:
            x = x.reshape(3, )

        return x


class XyzFile(AtomCo):
    """
    Create a .xyz file class.

    Example:

    >>> a = XyzFile(filename='ts.xyz')

    Class attributes descriptions
    =======================================================================
      Attribute      Description
      ============  =======================================================
      filename       string, name of the file the direct coordiante data
                     stored in
      natom          int, the number of total atom number
      step           int, STEP number in OUT.ANI file
      atom_types     list of string, atom types
      atom_numbers   list of int, atom number of atoms
      atomco_dict    dict, {atom name: coordinates}
      data           np.array, coordinates of atoms, dtype=float64
      ============  =======================================================
    """
    def __init__(self, **kwargs):
        filename = kwargs.pop("filename", None)
        content = kwargs.pop("content", None)
        content_list = kwargs.pop("content_list", None)

        if content_list is not None:
            content_list = content_list
        elif filename is not None:
            super(self.__class__, self).__init__(filename)
            with open(self.filename, 'r') as f:
                content_list = f.readlines()
        elif content is not None:
            content = content.strip()
            content_list = content.split("\n")

        self.load(content_list)
        self.verify()

    def load(self, content_list):
        """ Load all data in xyz file.
        """
        # Total number of all atoms.
        natom = int(content_list[0].strip())

        # The iteration step for this xyz file.
        step = int(str2list(content_list[1])[-1])

        # Get atom coordinate and number info
        data_list = [str2list(line) for line in content_list[2:]]
        data_array = np.array(data_list)      # dtype=np.string
        atoms_list = list(data_array[:, 0])   # 1st column
        data = np.float64(data_array[:, 1:])  # rest columns

        # Atom number for each atom
        atom_types = []
        for atom in atoms_list:
            if atom not in atom_types:
                atom_types.append(atom)
        atom_numbers = [atoms_list.count(atom) for atom in atom_types]

        # Set attributes.
        self.natom = natom
        self.step = step
        self.atom_types = atom_types
        self.atom_numbers = atom_numbers
        self.data = data

    def coordinate_transform(self, bases=None):
        "Use Ax=b to do coordinate transform cartesian to direct"
        if bases is None:
            bases = np.array([[1.0, 0.0, 0.0],
                              [0.0, 1.0, 0.0],
                              [0.0, 0.0, 1.0]])
        return self.cart2dir(bases, self.data)

    def get_content(self):
        "获取最新文件内容字符串"
        content = self.get_xyz_content()
        return content

    def tofile(self, filename='atomco.xyz'):
        "XyzFile object to .xyz file."
        content = self.get_content()

        with open(filename, 'w') as f:
            f.write(content)

        return

    def reduce_coordinate(self, **kwargs):
        "Reduce the coordinates that cross the crystal boundary"
        poscar = kwargs.pop('poscar', None)
        bases = kwargs.pop('bases', None)
        if poscar is not None:
            bases = poscar.bases * poscar.bases_const
        elif bases is not None:
            pass
        else:
            raise AssertionError('No POSCAR or bases passed in')
        for i, coordinate in enumerate(self.data):
            reduced_coordinate = np.linalg.solve(bases, coordinate) % 1.0
            self.data[i] = np.dot(bases, reduced_coordinate)

class PosCar(AtomCo):
    def __init__(self, filename='POSCAR'):
        """
        Class to generate POSCAR or CONTCAR-like objects.

        Example:

        >>> a = PosCar(filename='POSCAR')

        Class attributes descriptions
        =======================================================================
          Attribute      Description
          ============  =======================================================
          filename       string, name of the file the direct coordiante data
                         stored in
          bases_const    float, lattice bases constant
          bases          np.array, bases of POSCAR
          natom          int, the number of total atom number
          atom_types     list of strings, atom types
          atom_numbers   list of int, same shape with atoms
                         atom number of atoms in atoms
          tf             list of list, T&F info of atoms
          data           np.array, coordinates of atoms, dtype=float64
          ============  =======================================================
        """
        AtomCo.__init__(self, filename)

        # Load all data in file
        self.load()
        self.verify()

    def load(self):
        """ Load all information in POSCAR.
        """
        with open(self.filename, 'r') as f:
            content_list = f.readlines()

        # get scale factor
        bases_const = float(content_list[1])

        # bases
        bases = [str2list(basis) for basis in content_list[2:5]]

        # Atom info
        atom_types = str2list(content_list[5])
        # Atom number (str).
        atom_numbers = str2list(content_list[6])
        if content_list[7][0] in 'Ss':
            data_begin = 9
        else:
            data_begin = 8

        # get total number before load data
        atom_numbers = [int(i) for i in atom_numbers]
        natom = sum(atom_numbers)

        # data
        data, tf = [], []  # data and T or F info
        tf_dict = {}       # {tf: atom number}
        for line_str in content_list[data_begin: data_begin+natom]:
            line_list = str2list(line_str)
            data.append(line_list[:3])
            if len(line_list) > 3:
                tf_list = line_list[3:]
                tf.append(tf_list)
                # gather tf info to tf_dict
                tf_str = ','.join(tf_list)
                if tf_str not in tf_dict:
                    tf_dict[tf_str] = 1
                else:
                    tf_dict[tf_str] += 1
            else:
                tf.append(['T', 'T', 'T'])
                # gather tf info to tf_dict
                if 'T,T,T' not in tf_dict:
                    tf_dict['T,T,T'] = 1
                else:
                    tf_dict['T,T,T'] += 1

        # Data type convertion
        bases = np.float64(np.array(bases))  # to float
        data = np.float64(np.array(data))
        tf = np.array(tf)

        # set class attrs
        self.bases_const = bases_const
        self.bases = bases
        self.atom_types = atom_types
        self.atom_numbers = atom_numbers
        self.natom = natom
        self.data = data
        self.tf = tf
        self.totline = data_begin + natom  # total number of line

    def constrain_atom(self, atom, to='F', axis='all'):
        "修改某一类型原子的FT信息"
        # [1, 1, 1, 16] -> [0, 1, 2, 3, 19]
        idx_list = [sum(self.atom_numbers[:i])
                    for i in range(1, len(self.atom_types)+1)]
        idx_list = [0] + idx_list

        if to not in ['T', 'F']:
            raise CarfileValueError('Variable to must be T or F.')

        for atom_type, idx, next_idx in zip(self.atom_types,
                                            idx_list[:-1],
                                            idx_list[1:]):
            if atom_type == atom:
                if axis in ['x', 'X']:
                    self.tf[idx:next_idx, 0] = to
                elif axis in ['y', 'Y']:
                    self.tf[idx:next_idx, 1] = to
                elif axis in ['z', 'Z']:
                    self.tf[idx:next_idx, 2] = to
                else:
                    self.tf[idx:next_idx, :] = to
                break

        return self.tf

    def get_content(self):
        "根据对象数据获取文件内容字符串"
        content = self.get_poscar_content()
        return content

    def tofile(self, filename='POSCAR_c'):
        "生成文件"
        "PosCar object to POSCAR or CONTCAR."
        content = self.get_content()

        with open(filename, 'w') as f:
            f.write(content)

        return


class ContCar(PosCar):
    def __init__(self, filename='CONTCAR'):
        '''
        Class to generate POSCAR or CONTCAR-like objects.
        Totally same as PosCar class.

        Example:

        >>> a = ContCar(filename='POSCAR')
        '''
        PosCar.__init__(self, filename=filename)

    def tofile(self, filename='CONTCAR_c'):
        PosCar.tofile(self, filename=filename)


class XdatCar(AtomCo):
    def __init__(self, filename='XDATCAR'):
        """
        Class to generate XDATCAR objects.

        Example:

        >>> a = XdatCar()

        Class attributes descriptions
        =======================================================================
          Attribute      Description
          ============  =======================================================
          filename       string, name of the file the direct coordiante data
                         stored in
          bases_const    float, lattice bases constant
          bases          np.array, bases of POSCAR
          natom          int, the number of total atom number
          atom_types     list of strings, atom types
          tf             list of list, T&F info of atoms
          info_nline     int, line numbers of lattice info
          ============  =======================================================
        """
        AtomCo.__init__(self, filename)
        self.info_nline = 7  # line numbers of lattice info
        self.load()

    def load(self):
        with open(self.filename, 'r') as f:
            # read lattice info
            self.system = f.readline().strip()
            self.bases_const = float(f.readline().strip())

            # lattice basis
            self.bases = []
            for i in range(3):
                basis = line2list(f.readline())
                self.bases.append(basis)

            # atom info
            self.atom_types = str2list(f.readline())
            atoms_num = str2list(f.readline())
            self.atom_numbers = [int(i) for i in atoms_num]
            self.natom = sum(self.atom_numbers)

    def __iter__(self):
        """ Make the XdatCar object iterable.
        """
        # Define namedtuple for the item in iteration.
        XdatCarItem = namedtuple("XdatCarItem", ["step", "coordinates"])

        with open(self.filename, 'r') as f:
            # pass info lines
            for i in range(self.info_nline):
                f.readline()
            prompt = f.readline().strip()
            while '=' in prompt:
                step = int(prompt.split('=')[-1])
                data = []
                for i in range(self.natom):
                    data_line = f.readline()
                    data.append(line2list(data_line))
                prompt = f.readline().strip()

                yield XdatCarItem._make([step, np.array(data)])


class CifFile(AtomCo):
    def __init__(self, filename):
        """
        Class for *.cif files.

        Example:

        >>> a = CifFile(filename='ts.cif')

        Class attributes descriptions
        =======================================================================
          Attribute         Description
          ===============  ====================================================
          filename         string, name of the file the direct coordiante data
                           stored in
          natom            int, the number of total atom number
          atom_types       list of strings, atom types
          atom_numbers     list of int, atom number of atoms in atoms
          atom_names       list of string,
                           Value of attribute 'Name' in Atom3d tag.
          data             np.array, coordinates of atoms, dtype=float64

          cell_length_a    float, length of cell vector a
          cell_length_a    float, length of cell vector b
          cell_length_c    float, length of cell vector c
          cell_angle_alpha float, angle of cell alpha
          cell_angle_beta  float, angle of cell beta
          cell_angle_gamma float, angle of cell gamma
          ===============  ====================================================
        """
        super(CifFile, self).__init__(filename)
        self.__logger = logging.getLogger("vaspy.CifCar")
        self.load()

    def load(self):
        """
        Load data and attributes from *.cif file.
        """
        # Regular expression for attributes matching.
        regex = re.compile(r'^_(\w+)(?:\s+)(.+)$')

        with open(self.filename, 'r') as f:
            lines = f.readlines()

        # Split lines by 'loop_' indices.
        loop_indices = [i for i, line in enumerate(lines)
                        if line.startswith('loop_')]
        # [19, 23] -> [(0, 19), (20, 23), (24, line_length)]
        start_indices = [0] + [i + 1 for i in loop_indices]
        end_indices = loop_indices + [len(lines)]
        lines_groups = [lines[start: end] for start, end in
                        zip(start_indices, end_indices)]

        # Get attributes.
        float_candidates = ['cell_length_a', 'cell_length_b', 'cell_length_c',
                            'cell_angle_alpha', 'cell_angle_beta', 'cell_angle_gamma']
        for line in lines_groups[0]:
            line = line.strip()
            if line.startswith('_'):
                m = regex.match(line)
                if m:
                    attr, value = m.groups()
                    if attr in float_candidates:
                        value = float(value)
                    setattr(self, attr, value)
                    self.__logger.debug("{} = {}".format(attr, value))

        # Get coordinates data.
        titles = []
        data = []
        atom_names = []
        atom_types = []

        for line in lines_groups[-1]:
            line = line.strip()
            if line.startswith('_'):
                titles.append(line[1:])
            elif line:
                atom_name, _, x, y, z, _, _, atom_type = line2list(line, dtype=str)
                atom_names.append(atom_name)
                atom_types.append(atom_type)
                data.append([float(i) for i in (x, y, z)])

        # Set attributes.
        self.data = np.array(data)
        self.atom_names = atom_names
        self.atom_types = list(set(atom_types))
        self.atom_numbers = [atom_types.count(atom) for atom in self.atom_types]
        self.titles = titles
        self.natom = len(atom_names)

