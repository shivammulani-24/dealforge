# Sample data — SYNTHETIC

`ardent_precision_synthetic.csv` describes **Ardent Precision Components (SYNTHETIC)**, a fictional
company. Every figure was constructed by hand for testing and demonstration; none is a real
company's reported data. Currency INR, scale crores, fiscal year ending 31 March.

The FY2025 column deliberately equals the inputs of the independently verified case KA-DCF-03
(`docs/verification/independent-verification.md`): revenue 2,000, operating NWC 300
(250 + 175 + 25 − 125 − 25), cash 150, debt 400, leases 50, NCI 30, pension deficit 20,
non-operating assets 40, 100 basic shares. Running the KA-DCF-03 assumptions on this company
therefore must reproduce 31.2150 per share.

Internal consistency (checked by the importer): revenue − COGS − OpEx = EBIT; pre-tax − tax =
net income; assets = liabilities + equity; D&A ≤ COGS + OpEx; NWC 15% of revenue each year.
