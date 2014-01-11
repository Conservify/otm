#!/usr/bin/env python2

description = 'otm - display static memory of an elf file in a treemap'

"""
Copyright (C) 2014  Ludwig Ortmann <ludwig@spline.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
from os import path
import subprocess
import random
import re
import argparse


from pprint import pprint

import pylab
from matplotlib.patches import Rectangle

class Treemap:
    def __init__(self, tree):
        self.ax = pylab.subplot(111,aspect='equal')
        pylab.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.iterate(tree)

    def iterate(self, node, lower=[0,0], upper=[1,1], axis=0):
        axis = axis % 2
        self.draw_rectangle(lower, upper, node)
        width = upper[axis] - lower[axis]
        ns = node.get_size()
        #print node.name, "w:", width
        #print "node has", len(node.children)

        for child in node.children:
            #print "child:", child.name
            cs = child.get_size()
            upper[axis] = (lower[axis] + ((width * float(cs)) / ns))
            lo = list(lower)
            up = list(upper)
            self.iterate(child, lo, up, axis + 1)
            lower[axis] = upper[axis]

    def draw_rectangle(self, lower, upper, node):
        #print lower, upper
        r = Rectangle( lower, upper[0]-lower[0], upper[1] - lower[1],
                   edgecolor='k',
                   facecolor= node.get_color(),
                   label=node.name)
        self.ax.add_patch(r)

        rx, ry = r.get_xy()
        rw = r.get_width()
        rh = r.get_height()
        cx = rx + rw/2.0
        cy = ry + rh/2.0
        if isinstance(node, PathNode):
            t = node.name
            if rw * 3 < rh:
                t += ", "
            else:
                t += "\n"
            t += str(node.size) + ", " + node.otype
            c='w'
            if rw < rh:
                o = "vertical"
            else:
                o = "horizontal"

        else:
            t = node.name
            if node.isfile:
                c='k'
                o = 45
            else:
                return
        self.ax.annotate(
                t,
                (cx,cy),
                color=c,
                weight='bold', ha='center', va='center',
                rotation=o
                )

class PathTree():
    def __init__(self, name, path_dict):

        self.children = list()
        self.name = name
        self.size = None
        self.isfile = False

        print name

        subdirectories = list()
        for p in path_dict:
            if p == '':
                #print "content", p
                self.add_children(path_dict[p])
                self.isfile = True
            else:
                #print "entry", p
                subdirectories.append(p)

        cdict = dict()
        for pathname in subdirectories:
            parts = pathname.split("/", 1)
            if len(parts) == 1:
                x = parts[0]
                rest = ""
            else:
                x,rest = parts

            if not x in cdict:
                cdict[x] = dict()
            cdict[x][rest] = path_dict[pathname]
            #print "adding", pathname, "to", x

        for k in cdict:
            #pprint(v, indent=2)
            self.children.append(PathTree(k, cdict[k]))

        #print "size:", self.get_size()

    def __repr__(self):
        return self.name

    def add_children(self, obj_list):
        for obj in obj_list:
            self.children.append(PathNode(*obj))

    def get_size(self):
        if self.size is None:
            self.size = 0
            for c in self.children:
                self.size += c.get_size()
        return self.size

    def get_color(self):
        return (random.random(),random.random(),random.random())


class PathNode(PathTree):

    def __init__(self, name, line, size, otype, bind):
        self.children = []
        print "\t", name, otype
        self.name = name
        self.size = size
        self.line = line
        self.isfile = False
        self.otype = otype
        self.bind = bind


def parse_elf(filename, minimum_size=100, function_regex='', object_regex=''):
    """parse elf file into a {path: [(object, linenumber, size)]} dictionary"""

    # Use readelf to get object names, sizes and addresses
    # The output format is:
    # 339: 00005968  1694 FUNC    GLOBAL DEFAULT    1 vuprintf
    output = subprocess.check_output([
                "readelf",
                "-s",
                filename])

    # Use addr2line for all objects to get object paths.
    # Store path -> objects + sizes into a dictionary.
    paths = dict()
    lines = output.splitlines()
    i = 0
    while ".symtab" not in lines[i]:
        i += 1
    i += 2

    addressses = dict()
    for line in lines[i:]:
        #print "parsing line:", line
        foo = line.split()
        addressses[foo[1]] = foo

    out = subprocess.check_output([
        "addr2line",
        "-e",
        filename
        ] + addressses.keys())
    addr_paths = [l.split(":") for l in out.splitlines()]

    it = iter(addr_paths)
    for addr in addressses:
        p = it.next()
        foo = addressses[addr]
        size = foo[2]
        otype = foo[3]
        bind = foo[4]
        name = foo[-1]
        size = int(size)
        if size < minimum_size:
            continue
        pathname, lineno = p
        pathname = path.normpath(pathname)
        if pathname[0] == '/':
            pathname = pathname[1:]

        if otype == "FUNC":
            pat = function_regex
        elif otype == "OBJECT":
            pat = object_regex
        else:
            pat = ""
        if not re.search(pat, pathname):
            continue

        if not pathname in paths:
            paths[pathname] = list()
        paths[pathname].append((name, lineno, size, otype, bind))

    return paths

def arg_parser():
    p = argparse.ArgumentParser(description=description)

    p.add_argument("filename", default="a.out", nargs='?',
            help="the elf file to parse")

    p.add_argument("-d","--documentation",
            action="store_true", default=argparse.SUPPRESS,
            help="print additional documentation and exit")

    p.add_argument("-f", "--function-regex", default="",
            help="regular expression for function path filtering")
    p.add_argument("-o","--object-regex", default="",
            help="regular expression for object path filtering")
    p.add_argument("-m","--minimum-size", type=int, default=1,
            help="mininum size for all types")

    return p

def exit_doc():
    print """
Regular expression examples:
  --func-regex "xxxxxx"    # (probably) filter out functions completely
  --func-regex "net|core"  # display any function that comes from net or core
  --obj-regex "\?\?"       # display objects that readelf could not look up

Minumum size:
  The minimum-size argument is taken as an inclusion hurdle, i.e.
  objects/functions below that size are not taken into consideration at all.
"""
    sys.exit()

#TODO: use option parser
if __name__ == '__main__':
    args = arg_parser().parse_args()
    if hasattr(args,"documentation"):
        exit_doc()

    if not path.isfile(args.filename):
        sys.exit("file does not exist: " + args.filename)

    elf = parse_elf(**vars(args))
    tree = PathTree("root", elf)
    Treemap(tree)
    pylab.show()