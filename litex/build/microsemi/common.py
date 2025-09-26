#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

#from migen import *
#from migen.genlib.resetsync import AsyncResetSynchronizer
#from migen.fhdl.specials import Instance, Tristate

from migen.fhdl.module import Module
from migen.fhdl.specials import Instance, Tristate
from migen.fhdl.bitcontainer import value_bits_sign
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# AsyncResetSynchronizer ---------------------------------------------------------------------------

class MicrosemiAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("DFN1P0",
                i_CLK = cd.clk,
                i_PRE = ~async_reset,
                i_D   = 0,
                o_Q   = rst1
            ),
            Instance("DFN1P0",
                i_CLK = cd.clk,
                i_PRE = ~async_reset,
                i_D   = rst1,
                o_Q   = cd.rst
            )
        ]


class MicrosemiAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return MicrosemiAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


# ------- Common  SDRInput ---------------------

class MicrosemiSDRInputImpl(Module):
    def __init__(self, i, o ): 
        for j in range(len(i)):
            self.specials += Instance("INBUF",
                i_PAD   = i[j],
                o_Y   = o[j]
            )

class MicrosemiSDRInput:
    @staticmethod
    def lower(dr):
        return MicrosemiSDRInputImpl(dr.i, dr.o)   
 
 
# Common SDROutput   -------------------------------------------------------------------------------
class MicrosemiSDROutputImpl(Module):
    def __init__(self, i, o ):
        for j in range(len(o)):
            self.specials += Instance("OUTBUF",
                i_D   = i[j],
                o_PAD   = o[j]
            )

class MicrosemiSDROutput:
    @staticmethod
    def lower(dr):
        return MicrosemiSDROutputImpl(dr.i, dr.o)
    

# Common SDRTristate -------------------------------------------------------------------------------

class MicrosemiSDRTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        
        for j in range(len(io)):
            self.specials += Instance("BIBUF",
                io_PAD = io[j],
                o_Y   = i[j],
                i_D   = o[j],
                i_E   = oe[j],
            )

class MicrosemiSDRTristate:
    @staticmethod
    def lower(dr):
        return MicrosemiSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i)
    
    

# Special Overrides --------------------------------------------------------------------------------

microsemi_mpf_special_overrides = {
    AsyncResetSynchronizer: MicrosemiAsyncResetSynchronizer,
    Tristate:               MicrosemiSDRTristate,
#    DifferentialOutput:     LatticeiCE40DifferentialOutput,
#    DifferentialInput:      LatticeiCE40DifferentialInput,
#    DDROutput:              LatticeiCE40DDROutput,
#    DDRInput:               LatticeiCE40DDRInput,
    SDROutput:              MicrosemiSDROutput,
    SDRInput:               MicrosemiSDRInput,
    SDRTristate:            MicrosemiSDRTristate,
}

microsemi_m2s_special_overrides = {
    AsyncResetSynchronizer: MicrosemiAsyncResetSynchronizer,
    Tristate:               MicrosemiSDRTristate,
    SDROutput:              MicrosemiSDROutput,
    SDRInput:               MicrosemiSDRInput,
    SDRTristate:            MicrosemiSDRTristate,
}
