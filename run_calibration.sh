#!/bin/bash
# Run calibration sweep with different transmission rates

RATES="0.5 0.4 0.3 0.25 0.2 0.15 0.1"

echo "Calibration Sweep - Target: 250 infections"
echo "============================================"

for rate in $RATES; do
    echo ""
    echo "Testing rate=$rate..."
    INFECTION_TRANSMISSION_RATE=$rate python calib_single.py $rate 2>/dev/null | tail -1
done

echo ""
echo "Done!"
