import streamlit as st
import datetime
from doff10.query import get_dofftable_details
import pandas as pd
from WvgS4.s4effdaywise import s4_eff_daywise_view

s4_eff_daywise_view()
