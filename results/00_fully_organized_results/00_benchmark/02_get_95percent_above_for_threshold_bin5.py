import pandas as pd, numpy as np

# CSV produced by your script
df = pd.read_csv("stsb_miniLM_cosines.csv")

# Keep only the gold-label 5.0 pairs (“5” bin)
bin5 = df[df["bin"] == "5"]["cosine"].values.astype(float)

# Bottom-5 % threshold: 95 % of pairs lie above this value
threshold_5perc = np.percentile(bin5, 5)      # same as np.quantile(bin5, 0.05)

print(f"5th-percentile cosine in bin 5 = {threshold_5perc:.3f}")
