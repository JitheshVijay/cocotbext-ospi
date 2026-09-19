Waveforms
=========

Generated from real simulations rather than drawn by hand -- ``capture.py``
runs the transactions, Icarus dumps a VCD, and ``render.py`` samples it. They
cannot drift from what the models do.

Regenerate with::

    make -C docs/waveforms
    make -C docs/waveforms svg

.. figure:: waveforms/octal-read.svg
   :alt: Fast read octal I/O

   Fast read octal I/O

.. figure:: waveforms/width-comparison.svg
   :alt: One byte at every width

   One byte at every width

.. figure:: waveforms/read-status.svg
   :alt: Read status with WIP set

   Read status with WIP set
