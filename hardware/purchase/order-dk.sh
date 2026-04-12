#!/bin/bash
echo "=== Koe Seed Demo Kit — DigiKey Order ==="
echo ""
echo "Opening DigiKey cart with:"
echo "  3x nRF5340 Audio DK (NRF5340-AUDIO-DK) @ \$169 = \$507"
echo "  1x nRF21540 FEM EK  (NRF21540-EK)     @ \$30  = \$30"
echo "  Total: ~\$537 + overnight shipping ~\$50 = ~\$587"
echo ""
echo "DigiKey Part Numbers:"
echo "  1490-NRF5340-AUDIO-DK-ND  qty 3"
echo "  1490-NRF21540-EK-ND       qty 1"
echo ""

# Open DigiKey search pages
open "https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16399476"
open "https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF21540-EK/15299908"

echo "Add to cart, select overnight shipping to Japan, checkout."
echo ""
echo "Expected delivery: 2-3 business days (DHL Express)"
