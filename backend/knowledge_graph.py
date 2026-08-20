"""
ForgeSpec AI - Industrial Knowledge Graph Engine
Models relationships between products, categories, manufacturers, materials, certifications, and required attributes.
"""

from typing import Dict, List, Any

TAXONOMY_MANDATORY_ATTRIBUTES = {
    "Dishwashers": [
        "Voltage Rating", "Amperage Rating", "Sound Level", "Mounting Type",
        "Material", "Number of Wash Cycles", "Depth With Door Open"
    ],
    "Cut-Off Discs": [
        "Wheel Diameter", "Thickness", "Arbor Hole Size", "Abrasive Material", "Maximum Speed"
    ],
    "PVC Deck Boards": [
        "Nominal Dimensions", "Actual Width", "Length", "Edge Profile", "Color", "Material"
    ]
}

class KnowledgeGraphEngine:
    @staticmethod
    def inspect_product_graph(product: Dict[str, Any], extracted_labels: List[str]) -> Dict[str, Any]:
        category = product.get("fine", "Dishwashers")
        required_attrs = TAXONOMY_MANDATORY_ATTRIBUTES.get(category, [])
        
        missing = [req for req in required_attrs if req not in extracted_labels]
        completeness = round(((len(required_attrs) - len(missing)) / max(1, len(required_attrs))) * 100, 1)

        nodes = [
            {"id": product["mfg_part_num"], "label": product["mfg_part_num"], "type": "Product", "size": 28},
            {"id": product["brand_name"], "label": product["brand_name"], "type": "Brand", "size": 20},
            {"id": category, "label": category, "type": "Category", "size": 22},
            {"id": product["mfg_name"], "label": product["mfg_name"], "type": "Manufacturer", "size": 18}
        ]

        edges = [
            {"source": product["mfg_part_num"], "target": product["brand_name"], "relation": "BRANDED_AS"},
            {"source": product["mfg_part_num"], "target": category, "relation": "BELONGS_TO"},
            {"source": product["mfg_part_num"], "target": product["mfg_name"], "relation": "MANUFACTURED_BY"}
        ]

        # Add certifications to graph
        for cert in product.get("standard_approvals", []):
            nodes.append({"id": cert, "label": cert, "type": "Certification", "size": 16})
            edges.append({"source": product["mfg_part_num"], "target": cert, "relation": "CERTIFIED_BY"})

        return {
            "category": category,
            "required_attributes": required_attrs,
            "missing_attributes": missing,
            "completeness_percentage": completeness,
            "graph_data": {
                "nodes": nodes,
                "edges": edges
            }
        }
