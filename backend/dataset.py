"""
ForgeSpec AI - Sample Industrial Product Dataset
Contains high-fidelity dataset records modeled from the UniHack Challenge dataset.
"""

INDUSTRIAL_DATASET = [
    {
        "id": "PDSH4816AF",
        "sku": "1515863",
        "mfg_part_num": "PDSH4816AF",
        "part_desc": "PDSH4816AF Dishwasher SS - Display Only",
        "mfg_name": "Rheem Manufacturing / Frigidaire",
        "brand_name": "FRIGIDAIRE®",
        "trade_name": "Professional Series",
        "dept": "Appliances",
        "class": "Large Appliances",
        "fine": "Dishwashers",
        "classpath": "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers",
        "short_desc": "FRIGIDAIRE® Professional Series PDSH4816AF Dishwasher With CleanBoost™, Leg Mounting, 5-Wash Cycle, Stainless Steel",
        "long_desc": "FRIGIDAIRE® Dishwasher With CleanBoost™, Professional Series, 5 Wash Cycles, 120 V, 15 A, Leg Mounting, 24 in W x 24-1/4 in D, 50-1/4 in Depth With Door Open, 8-1/2 in Upper Rack, 11-1/4 in Lower Rack Minimum Height, 10-3/8 in Upper Rack, 13-1/4 in Lower Rack Maximum Height, 47 dBA Sound Level, Stainless Steel, Additional Information: 240 kW-hr Annual Energy, 1 to 12 hr Delay Start Hours",
        "mobile_desc": "DISHWASHER LEG 5 SST 120V 15A 50-1/4IN",
        "invoice_desc": "FRIGIDAIRE Dishwasher Professional Series",
        "retail_desc": "Professional Series Dishwasher, Leg Mounting, 5-Wash Cycle, Stainless Steel",
        "marketing_desc": "Get dishes clean on the first wash with CleanBoost™ Technology which delivers target water flow directly to dishes.",
        "mfr_url": "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF",
        "ref_urls": [
            "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF",
            "https://www.appliance-parts-direct.com/item/PDSH4816AF",
            "https://www.industrial-distributor.com/catalog/appliances/PDSH4816AF"
        ],
        "pdf_document": "FRIGIDAIRE_PDSH4816AF_Specification_Sheet.pdf",
        "pdf_pages": 2,
        "standard_approvals": ["ASSE 1006", "CEE Tier 2 Qualified", "cUL Listed", "ENERGY STAR Certified", "NSF Certified", "UL Listed"],
        "raw_attributes": [
            {"label": "Series", "value": "Professional Series", "uom": ""},
            {"label": "Number of Wash Cycles", "value": "5", "uom": ""},
            {"label": "Voltage Rating", "value": "120", "uom": "V"},
            {"label": "Amperage Rating", "value": "15", "uom": "A"},
            {"label": "Mounting Type", "value": "Leg", "uom": ""},
            {"label": "Size", "value": "24 in W x 24-1/4 in D", "uom": "in"},
            {"label": "Depth With Door Open", "value": "50-1/4", "uom": "in"},
            {"label": "Minimum Height", "value": "8-1/2 in Upper Rack, 11-1/4 in Lower Rack", "uom": "in"},
            {"label": "Maximum Height", "value": "10-3/8 in Upper Rack, 13-1/4 in Lower Rack", "uom": "in"},
            {"label": "Sound Level", "value": "47", "uom": "dBA"},
            {"label": "Material", "value": "Stainless Steel", "uom": ""},
            {"label": "Annual Energy Consumption", "value": "240", "uom": "kW-hr"},
            {"label": "Delay Start Hours", "value": "1 to 12", "uom": "hr"}
        ],
        "conflicts": [
            {
                "attribute": "Amperage Rating",
                "source_1": {"name": "Manufacturer PDF Datasheet", "value": "15 A", "authority": 0.95},
                "source_2": {"name": "Ref URL 2 (Retail Portal)", "value": "10 A", "authority": 0.60},
                "resolution": "15 A",
                "reason": "Manufacturer PDF datasheet holds higher domain authority (0.95 vs 0.60)."
            },
            {
                "attribute": "Sound Level",
                "source_1": {"name": "Manufacturer PDF Datasheet", "value": "47 dBA", "authority": 0.95},
                "source_2": {"name": "Ref URL 3 (Distributor CSV)", "value": "52 dBA", "authority": 0.45},
                "resolution": "47 dBA",
                "reason": "47 dBA verified on page 2 paragraph 4 of official spec sheet."
            }
        ],
        "pdf_spatial_evidence": {
            "Sound Level": {"page": 1, "bbox": [120, 310, 280, 328], "text": "47 dBA Sound Level, Ultra Quiet Operation"},
            "Voltage Rating": {"page": 1, "bbox": [120, 280, 240, 298], "text": "Voltage Rating: 120 V, 15 A Electrical Supply"},
            "Depth With Door Open": {"page": 2, "bbox": [80, 140, 310, 158], "text": "50-1/4 in Depth With Door Open (1276.35 mm)"},
            "Annual Energy Consumption": {"page": 2, "bbox": [80, 420, 300, 438], "text": "Additional Information: 240 kW-hr Annual Energy"}
        }
    },
    {
        "id": "WDTS7024RZ",
        "sku": "1515867",
        "mfg_part_num": "WDTS7024RZ",
        "part_desc": "WDTS7024RZ Dishwasher SS - Display Only",
        "mfg_name": "Whirlpool Corporation",
        "brand_name": "Whirlpool®",
        "trade_name": "Eco Series",
        "dept": "Appliances",
        "class": "Large Appliances",
        "fine": "Dishwashers",
        "classpath": "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers",
        "short_desc": "Whirlpool® Eco Series WDTS7024RZ Dishwasher, Built-in Mounting, Stainless Steel",
        "long_desc": "Whirlpool® Dishwasher, Eco Series, 120 V, 10 A, Built-in Mounting, 33-7/16 in H x 23-7/8 in W x 22-5/8 in D, 50-3/16 in Depth With Door Open, 33-7/16 in Minimum Height, 41 dBA Sound Level, Stainless Steel, Additional Information: Folding Tines, Leak Detection System, Moisture Repellent Silverware Basket, Triple Wash Spray",
        "mobile_desc": "DISHWASHER BLTLN SST SST 120V 10A 41DBA",
        "invoice_desc": "Whirlpool Dishwasher Eco Series",
        "retail_desc": "Eco Series Dishwasher, Built-in Mounting, Stainless Steel",
        "marketing_desc": "Load more and run less with our quietest and largest capacity dishwasher featuring 3rd rack wash action.",
        "mfr_url": "https://www.whirlpool.com/smartsearchresults?searchtext=WDTS7024R",
        "ref_urls": [
            "https://www.whirlpool.com/smartsearchresults?searchtext=WDTS7024R",
            "https://www.whirlpool.com/content/dam/global/documents/202412/owners-manual-w11323304-revj.pdf",
            "https://www.whirlpool.com/content/dam/global/documents/202406/installation-instructions-w11323304-revG.pdf"
        ],
        "pdf_document": "Whirlpool_WDTS7024RZ_Specification_Sheet.pdf",
        "pdf_pages": 4,
        "standard_approvals": ["ENERGY STAR Certified", "UL Listed", "NSF Sanitize Certified"],
        "raw_attributes": [
            {"label": "Series", "value": "Eco Series", "uom": ""},
            {"label": "Voltage Rating", "value": "120", "uom": "V"},
            {"label": "Amperage Rating", "value": "10", "uom": "A"},
            {"label": "Mounting Type", "value": "Built-in", "uom": ""},
            {"label": "Size", "value": "33-7/16 in H x 23-7/8 in W x 22-5/8 in D", "uom": "in"},
            {"label": "Depth With Door Open", "value": "50-3/16", "uom": "in"},
            {"label": "Sound Level", "value": "41", "uom": "dBA"},
            {"label": "Material", "value": "Stainless Steel", "uom": ""}
        ],
        "conflicts": [],
        "pdf_spatial_evidence": {
            "Sound Level": {"page": 1, "bbox": [100, 200, 260, 218], "text": "Quiet 41 dBA Sound Level with 3rd Rack"},
            "Amperage Rating": {"page": 1, "bbox": [100, 250, 220, 268], "text": "Electrical Requirements: 120V AC, 10A branch circuit"}
        }
    },
    {
        "id": "49-94-0013",
        "sku": "4031-0013",
        "mfg_part_num": "49-94-0013",
        "part_desc": "49-94-0013 Milw 5\"x.045\"x7/8\" Metal Cut Off Disc",
        "mfg_name": "Milwaukee Tool / Milwaukee Accessory",
        "brand_name": "Milwaukee®",
        "trade_name": "Performance+",
        "dept": "Tools & Accessories",
        "class": "Abrasives & Cutting Tools",
        "fine": "Cut-Off Discs",
        "classpath": "Tools & Abrasives>Abrasive Discs>Cut-Off Wheels",
        "short_desc": "Milwaukee® 5 in x 0.045 in x 7/8 in Metal Cut Off Disc",
        "long_desc": "Milwaukee® 5 in Outer Diameter x 0.045 in Thickness x 7/8 in Arbor Hole Metal Cut Off Wheel, Aluminum Oxide Abrasive Grain, 12,250 Max RPM",
        "mobile_desc": "MILW 5X.045X7/8 MET CUTOFF DISC",
        "invoice_desc": "Milwaukee 5 in Cut Off Wheel",
        "retail_desc": "5 in x .045 in x 7/8 in Metal Cut Off Disc",
        "marketing_desc": "Engineered with high performance aluminum oxide grain for fast cutting and longer life in metal cutting applications.",
        "mfr_url": "https://www.milwaukeetool.com/Accessories/Abrasives/49-94-0013",
        "ref_urls": [
            "https://www.milwaukeetool.com/Accessories/Abrasives/49-94-0013",
            "https://www.industrial-supplies.com/milwaukee-49-94-0013"
        ],
        "pdf_document": "Milwaukee_49-94-0013_SpecSheet.pdf",
        "pdf_pages": 1,
        "standard_approvals": ["ANSI B7.1 Certified", "OSHA Compliant"],
        "raw_attributes": [
            {"label": "Wheel Diameter", "value": "5", "uom": "in"},
            {"label": "Thickness", "value": "0.045", "uom": "in"},
            {"label": "Arbor Hole Size", "value": "7/8", "uom": "in"},
            {"label": "Abrasive Material", "value": "Aluminum Oxide", "uom": ""},
            {"label": "Maximum Speed", "value": "12250", "uom": "RPM"},
            {"label": "Applicable Materials", "value": "Steel, Stainless Steel, Sheet Metal", "uom": ""}
        ],
        "conflicts": [
            {
                "attribute": "Arbor Hole Size",
                "source_1": {"name": "Milwaukee Tech Spec Sheet", "value": "7/8 in (22.23 mm)", "authority": 0.98},
                "source_2": {"name": "Vendor CSV Import", "value": "5/8 in", "authority": 0.35},
                "resolution": "7/8 in",
                "reason": "Verified against physical tool arbor spec. 5/8 in is for 4-1/2 in series."
            }
        ],
        "pdf_spatial_evidence": {
            "Wheel Diameter": {"page": 1, "bbox": [50, 110, 200, 128], "text": "5 in Outer Diameter x 0.045 in Thickness"},
            "Arbor Hole Size": {"page": 1, "bbox": [50, 130, 210, 148], "text": "7/8 in (22.23 mm) Arbor Hole Fitting"}
        }
    },
    {
        "id": "ADB15516CS",
        "sku": "PARK-6151-CS16",
        "mfg_part_num": "ADB15516CS",
        "part_desc": "1x6-16' Coastline Sq Edge - Vintage Azek PVC Decking",
        "mfg_name": "TimberTech / Azek Building Products",
        "brand_name": "TIMBERTECH®",
        "trade_name": "Vintage Collection",
        "dept": "Building Materials",
        "class": "Decking & Railing",
        "fine": "PVC Deck Boards",
        "classpath": "Building Materials>Decking>Synthetic Deck Boards",
        "short_desc": "TimberTech® Vintage Collection 1 in x 6 in x 16 ft Coastline Square Edge PVC Decking Board",
        "long_desc": "TimberTech® Vintage Collection 1 in x 5.5 in Actual Dimensions x 16 ft Length Coastline Color Square Edge Advanced PVC Decking Board with Alloy Armour Technology™",
        "mobile_desc": "1X6-16 FT COASTLINE SQ EDGE AZEK PVC",
        "invoice_desc": "TimberTech Coastline 16ft Square Edge",
        "retail_desc": "1x6 16ft Coastline Square Edge Vintage PVC Decking",
        "marketing_desc": "Delivers rich, multi-tonal wood aesthetics with high performance capped polymer PVC durability.",
        "mfr_url": "https://www.timbertech.com/products/decking/vintage-collection/coastline",
        "ref_urls": [
            "https://www.timbertech.com/products/decking/vintage-collection/coastline",
            "https://www.parksite.com/products/timbertech-vintage"
        ],
        "pdf_document": "TimberTech_Vintage_Azek_Decking_Catalog.pdf",
        "pdf_pages": 6,
        "standard_approvals": ["Class A Flame Spread Rating", "ESR-1667 ICC-ES Approved"],
        "raw_attributes": [
            {"label": "Nominal Dimensions", "value": "1 in x 6 in", "uom": "in"},
            {"label": "Actual Width", "value": "5.5", "uom": "in"},
            {"label": "Actual Thickness", "value": "1.0", "uom": "in"},
            {"label": "Length", "value": "16", "uom": "ft"},
            {"label": "Edge Profile", "value": "Square Edge", "uom": ""},
            {"label": "Color", "value": "Coastline", "uom": ""},
            {"label": "Material", "value": "Capped PVC / Polymer", "uom": ""}
        ],
        "conflicts": [],
        "pdf_spatial_evidence": {
            "Length": {"page": 3, "bbox": [90, 180, 250, 198], "text": "Available in 12 ft, 16 ft, and 20 ft Lengths"},
            "Actual Width": {"page": 3, "bbox": [90, 210, 240, 228], "text": "Actual Dimensions: 1.0 in x 5.5 in"}
        }
    }
]
