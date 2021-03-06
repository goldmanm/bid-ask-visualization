#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script saves bid and ask data for specified ETFs to files for each day
during market open hours.

It assumes the computer is at US East Coast Time.

@author: mark
"""

import os
import sys
import time 

import pandas as pd
import numpy as np

import alpaca_trade_api as ati
from datetime import datetime

import unittest
from get_quotes_alpaca_polygon import get_time_averages

s = pd.Series({0:5, 1:6, 2:7})
averages = get_time_averages(s, 1, 0 , 4)
correct_averages = [5, 6, 7, 7]
assert 4 == len(averages)
for a, b in zip(averages.values, correct_averages):
    assert a == b

s = pd.Series({0:5, 0.5:6, 2.5:7, 3.5:8})
averages = get_time_averages(s, 1, 0 , 4)
correct_averages = [5.5, 6, 6.5, 7.5]
assert 4 == len(averages)
for a, b in zip(averages.values, correct_averages):
    assert a == b
    
s = pd.Series({0:5, 0.1:6, 1.75:7, 2:8})
averages = get_time_averages(s, 1, 0 , 4)
correct_averages = [5.9, 6.25, 8, 8]
assert 4 == len(averages)
for a, b in zip(averages.values, correct_averages):
    assert a == b
