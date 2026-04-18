from __future__ import annotations

import re


STUDY_SEED_SOURCE = "study_v4"
PRODUCT_NOTE_SAMPLE_LIMIT = 2


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _topic_id(exam_code: str, subject_key: str, name: str, explicit_id: str | None = None) -> str:
    if explicit_id:
        return explicit_id
    return f"topic_{exam_code.lower()}_{subject_key}_{_slug(name)}"


def _subtopic_id(topic_id: str, order: int, name: str) -> str:
    return f"subtopic_{topic_id}_{order}_{_slug(name)}"


def _question_id(topic_id: str, kind: str, index: int) -> str:
    return f"question_{topic_id}_{kind}_{index}"


def _default_learning_objectives(name: str, subtopics: list[str], exam_code: str) -> list[str]:
    lead = subtopics[:3] if subtopics else [name]
    if exam_code == "UPSC":
        return [
            f"Explain the core dimensions of {name}.",
            f"Use {lead[0]} and {lead[min(1, len(lead) - 1)]} in a structured answer.",
            f"Link {name} with current exam-relevant implications.",
        ]
    return [
        f"Cover the core concepts of {name}.",
        f"Practice {lead[0]} and {lead[min(1, len(lead) - 1)]} through objective questions.",
        f"Revise shortcuts, traps, and common exam patterns in {name}.",
    ]


def _default_knowledge(name: str, description: str, subtopics: list[str], exam_code: str) -> dict:
    concept_a = subtopics[0] if subtopics else name
    concept_b = subtopics[1] if len(subtopics) > 1 else f"{name} applications"
    concept_c = subtopics[2] if len(subtopics) > 2 else f"{name} relevance"
    if exam_code == "UPSC":
        return {
            "keywords": [name, concept_a, concept_b, concept_c],
            "must_have_points": [
                f"{name} should be defined precisely before analysis begins",
                f"{concept_a} and {concept_b} are core dimensions of {name}",
                f"{name} must be linked to governance, society, or policy relevance",
            ],
            "good_to_have_points": [
                f"{concept_a} should be supported with a clear sub-dimension or example",
                f"{concept_b} helps structure the body of an exam answer",
                f"{concept_c} strengthens the conclusion and applied relevance",
            ],
            "extra_edge_points": [
                f"{name} can be connected with constitutional, administrative, or developmental implications",
                f"A balanced answer on {name} should include both opportunities and limitations",
            ],
            "core_facts": [
                f"{name} is a recurring syllabus area in {exam_code} preparation",
                f"{concept_a} and {concept_b} are reliable anchors for revision",
                f"{concept_c} helps convert basic recall into a higher-quality answer",
            ],
            "classification": [{"title": f"{name} map", "items": subtopics[:4] or [name]}],
            "case_laws": [],
            "current_affairs_seed": [],
            "mains_frame": {
                "intro": [f"Introduce {name} with a crisp definition and context line."],
                "body": [f"Explain {concept_a}", f"Analyse {concept_b}", f"Add {concept_c} with relevance"],
                "conclusion": [f"Conclude with the wider significance of {name}."],
            },
            "value_addition": [f"{name} framework", f"{concept_a} linkage", f"{concept_b} lens"],
            "pyq": [f"Discuss {name} and examine its significance in the syllabus context."],
        }
    return {
        "keywords": [name, concept_a, concept_b, concept_c],
        "must_have_points": [
            f"{name} fundamentals must be clear before solving questions",
            f"{concept_a} and {concept_b} are repeatedly tested areas in {exam_code}",
            f"{name} requires accuracy, recall speed, and elimination discipline",
        ],
        "good_to_have_points": [
            f"{concept_a} should be revised through timed practice",
            f"{concept_b} is a common source of mistakes and confusion",
            f"{concept_c} improves question-solving accuracy",
        ],
        "extra_edge_points": [
            f"{name} improves with pattern recognition and repeated drills",
            f"Short concept summaries make {name} easier to retain",
        ],
        "core_facts": [
            f"{name} is part of the {exam_code} syllabus backbone",
            f"{concept_a} and {concept_b} are high-yield revision anchors",
            f"Consistent MCQ practice helps stabilize performance in {name}",
        ],
        "classification": [{"title": f"{name} coverage", "items": subtopics[:4] or [name]}],
        "case_laws": [],
        "current_affairs_seed": [],
        "mains_frame": {"intro": [], "body": [], "conclusion": []},
        "value_addition": [f"{name} quick rules", f"{concept_a} shortcut", f"{concept_b} trap watch"],
        "pyq": [],
    }


def _make_topic(
    *,
    exam_code: str,
    subject_key: str,
    name: str,
    description: str,
    subtopics: list[str],
    difficulty: str = "medium",
    estimated_minutes: int = 50,
    explicit_id: str | None = None,
    code: str | None = None,
    learning_objectives: list[str] | None = None,
    knowledge: dict | None = None,
) -> dict:
    topic_id = _topic_id(exam_code, subject_key, name, explicit_id)
    return {
        "id": topic_id,
        "code": code or _slug(name).upper(),
        "name": name,
        "description": description,
        "subtopics": subtopics,
        "learning_objectives": learning_objectives or _default_learning_objectives(name, subtopics, exam_code),
        "difficulty": difficulty,
        "estimated_minutes": estimated_minutes,
        "knowledge": knowledge or _default_knowledge(name, description, subtopics, exam_code),
    }


FUNDAMENTAL_RIGHTS_KNOWLEDGE = {
    "keywords": ["Article 14", "Article 19", "Article 21", "reasonable restrictions", "judicial review", "writs"],
    "must_have_points": [
        "Fundamental Rights protect liberty and limit arbitrary state action",
        "Articles 14, 19 and 21 form the core liberty triangle",
        "Rights are enforceable through constitutional remedies under Article 32",
    ],
    "good_to_have_points": [
        "Reasonable restrictions balance individual liberty with public order and security",
        "Judiciary has expanded rights through progressive interpretation",
        "Writ jurisdiction under Articles 32 and 226 strengthens enforcement",
    ],
    "extra_edge_points": [
        "The post-Maneka Gandhi reading links procedure with fairness and due process",
        "Rights are central to constitutional morality and democratic legitimacy",
    ],
    "core_facts": [
        "Part III covers Articles 12 to 35",
        "Article 32 is called the heart and soul of the Constitution",
        "Article 21 has been judicially expanded beyond mere animal existence",
    ],
    "classification": [
        {
            "title": "Types of rights",
            "items": [
                "Equality",
                "Freedom",
                "Protection against exploitation",
                "Freedom of religion",
                "Cultural and educational rights",
                "Constitutional remedies",
            ],
        }
    ],
    "case_laws": [
        "Maneka Gandhi v Union of India",
        "Kesavananda Bharati v State of Kerala",
        "Puttaswamy v Union of India",
    ],
    "current_affairs_seed": [
        {
            "issue": "Digital personal data protection and privacy debates",
            "explanation": "Recent policy debates have revived questions around privacy, state surveillance, and informational autonomy.",
            "static_linkage": "Connect to Article 21 and the right to privacy jurisprudence.",
            "upsc_relevance": "Useful for GS2 polity, governance, rights, and essay framing.",
        }
    ],
    "mains_frame": {
        "intro": ["Define Fundamental Rights as enforceable constitutional guarantees against arbitrary power."],
        "body": ["Explain constitutional scope", "Show judicial evolution", "Mention balance through restrictions"],
        "conclusion": ["Conclude with liberty, dignity, and democratic accountability."],
    },
    "value_addition": ["Liberty-security balance", "Constitutional morality", "Transformative constitutionalism"],
    "pyq": [
        "Discuss the expanding scope of Article 21 in contemporary India.",
        "How do Fundamental Rights and Directive Principles complement each other?",
    ],
}


FEDERALISM_KNOWLEDGE = {
    "keywords": ["Union-state relations", "Seventh Schedule", "GST Council", "Inter-State Council", "cooperative federalism"],
    "must_have_points": [
        "Indian federalism combines a strong Union with constitutionally guaranteed state space",
        "Legislative, administrative, and fiscal dimensions define federal balance",
        "Cooperative federalism depends on consultation and institutional trust",
    ],
    "good_to_have_points": [
        "GST Council reflects negotiated fiscal federalism",
        "Use of governors and centrally driven schemes can trigger political friction",
        "The Inter-State Council remains underutilized",
    ],
    "extra_edge_points": [
        "Federalism in India is both constitutional design and political practice",
        "Asymmetric arrangements can stabilize diversity when used prudently",
    ],
    "core_facts": [
        "Seventh Schedule distributes powers across Union, State, and Concurrent Lists",
        "Article 263 provides for an Inter-State Council",
        "Fiscal federalism involves Finance Commission transfers and GST compensation architecture",
    ],
    "classification": [{"title": "Dimensions", "items": ["Legislative", "Administrative", "Fiscal", "Political"]}],
    "case_laws": ["S.R. Bommai v Union of India", "State of West Bengal v Union of India"],
    "current_affairs_seed": [
        {
            "issue": "Recurring disputes over governors, state finances, and centrally sponsored schemes",
            "explanation": "Recent disputes show that federalism remains a live political and administrative question.",
            "static_linkage": "Connect with cooperative federalism, constitutional morality, and fiscal trust.",
            "upsc_relevance": "High relevance for GS2 polity and governance answers.",
        }
    ],
    "mains_frame": {
        "intro": ["Define Indian federalism as quasi-federal in structure but increasingly negotiated in practice."],
        "body": ["Explain design", "Discuss current stress points", "Suggest institutional reforms"],
        "conclusion": ["Conclude that cooperative federalism is essential for effective governance."],
    },
    "value_addition": ["Negotiated federalism", "Fiscal trust deficit", "Asymmetrical federalism"],
    "pyq": [
        "How has competitive federalism changed Union-State relations?",
        "Discuss the role of institutions in strengthening cooperative federalism.",
    ],
}


INFLATION_KNOWLEDGE = {
    "keywords": ["CPI", "inflation targeting", "repo rate", "core inflation", "food inflation", "MPC"],
    "must_have_points": [
        "Inflation reflects sustained increase in the general price level",
        "CPI-driven inflation is central to welfare and policy debate",
        "Monetary policy balances inflation control with growth concerns",
    ],
    "good_to_have_points": [
        "Food and fuel shocks can have supply-side origins",
        "Core inflation indicates sticky price pressures",
        "Transmission of repo changes to the real economy is uneven",
    ],
    "extra_edge_points": [
        "Persistently high inflation hurts the poor the most through regressive welfare effects",
        "Policy needs coordination between monetary, fiscal, and supply-side tools",
    ],
    "core_facts": [
        "MPC targets headline CPI inflation",
        "Demand-pull and cost-push inflation have distinct drivers",
        "Headline inflation can diverge from core inflation due to volatile components",
    ],
    "classification": [{"title": "Types", "items": ["Demand-pull", "Cost-push", "Imported", "Core", "Headline"]}],
    "case_laws": [],
    "current_affairs_seed": [
        {
            "issue": "Persistent food inflation and monetary policy trade-offs",
            "explanation": "Recent inflation trends have highlighted the limits of rate action when supply shocks dominate.",
            "static_linkage": "Connect with inflation targeting, food supply chains, and welfare effects.",
            "upsc_relevance": "Important for GS3 economy and essay questions on growth versus stability.",
        }
    ],
    "mains_frame": {
        "intro": ["Define inflation and briefly note why it matters for welfare and macroeconomic stability."],
        "body": ["Explain drivers", "Assess impact", "Discuss policy toolkit"],
        "conclusion": ["Conclude on the need for coordinated policy and supply resilience."],
    },
    "value_addition": ["Inflation tax", "Sticky core inflation", "Growth-inflation trade-off"],
    "pyq": [
        "How does inflation affect different sections of society differently?",
        "Discuss the effectiveness of inflation targeting in India.",
    ],
}


MSP_KNOWLEDGE = {
    "keywords": ["MSP", "procurement", "PDS", "cropping pattern", "food security", "CACP"],
    "must_have_points": [
        "MSP aims to provide remunerative prices and reduce farmer distress",
        "Procurement supports buffer stocks and the public distribution system",
        "MSP-led incentives can distort cropping patterns and input use",
    ],
    "good_to_have_points": [
        "Implementation remains concentrated in a few crops and states",
        "Food security and ecological sustainability need joint consideration",
        "Market reforms and income support can complement MSP policy",
    ],
    "extra_edge_points": [
        "A procurement-heavy regime can create regional imbalance and fiscal stress",
        "Future reform must move from price assurance alone to broader risk management",
    ],
    "core_facts": [
        "CACP recommends MSP for multiple crops",
        "Procurement is much stronger for paddy and wheat than for pulses and oilseeds",
        "Food security involves availability, access, affordability, and nutrition",
    ],
    "classification": [{"title": "Policy angles", "items": ["Farmer income", "Food security", "Fiscal cost", "Ecology", "Regional equity"]}],
    "case_laws": [],
    "current_affairs_seed": [
        {
            "issue": "Ongoing debates on legal guarantee for MSP and procurement reform",
            "explanation": "Current policy debate links farm distress, procurement design, and food inflation.",
            "static_linkage": "Connect with agricultural marketing, fiscal sustainability, and nutrition security.",
            "upsc_relevance": "Highly useful for GS3 agriculture and economy questions.",
        }
    ],
    "mains_frame": {
        "intro": ["Introduce MSP as both income support and food system policy."],
        "body": ["Explain rationale", "Show distortions", "Suggest balanced reforms"],
        "conclusion": ["Conclude with a shift toward inclusive and sustainable farm support."],
    },
    "value_addition": ["Nutritional security", "Crop diversification", "Risk management architecture"],
    "pyq": [
        "How does procurement policy shape India’s agricultural outcomes?",
        "Critically examine the MSP regime in India.",
    ],
}


FISCAL_DEFICIT_KNOWLEDGE = {
    "keywords": ["fiscal deficit", "capital expenditure", "revenue expenditure", "crowding out", "FRBM", "public debt"],
    "must_have_points": [
        "Fiscal deficit measures the gap between total expenditure and total receipts excluding borrowings",
        "Quality of spending matters as much as the size of deficit",
        "Capital expenditure can have stronger multiplier effects than revenue spending",
    ],
    "good_to_have_points": [
        "High deficits can raise debt servicing burden and crowding-out risks",
        "Counter-cyclical fiscal policy can be justified during slowdowns",
        "Fiscal consolidation should protect growth-enhancing expenditure",
    ],
    "extra_edge_points": [
        "The fiscal debate is ultimately about credibility, composition, and inter-generational burden",
        "Off-budget liabilities can understate actual fiscal stress",
    ],
    "core_facts": [
        "FRBM framework seeks fiscal discipline",
        "Capital expenditure often creates future productive assets",
        "Borrowing for consumption and borrowing for assets have different macro effects",
    ],
    "classification": [{"title": "Assessment lenses", "items": ["Size", "Composition", "Debt sustainability", "Growth multiplier", "Transparency"]}],
    "case_laws": [],
    "current_affairs_seed": [
        {
            "issue": "Budget emphasis on public capex and fiscal consolidation",
            "explanation": "Recent budgets highlight the balancing act between growth support and fiscal prudence.",
            "static_linkage": "Connect with multiplier effects, debt sustainability, and fiscal credibility.",
            "upsc_relevance": "Important for GS3 economy and budget questions.",
        }
    ],
    "mains_frame": {
        "intro": ["Define fiscal deficit and mention why composition matters."],
        "body": ["Explain implications", "Differentiate expenditure quality", "Suggest reform path"],
        "conclusion": ["Conclude with responsible but growth-supportive consolidation."],
    },
    "value_addition": ["Quality of deficit", "Counter-cyclical policy", "Crowding out versus crowding in"],
    "pyq": [
        "Why is the quality of public expenditure important in deficit discussions?",
        "Discuss the relation between fiscal deficit and capital expenditure.",
    ],
}


PROBITY_KNOWLEDGE = {
    "keywords": ["probity", "integrity", "accountability", "transparency", "public office", "conflict of interest"],
    "must_have_points": [
        "Probity refers to uprightness, integrity, and adherence to ethical standards in public life",
        "Probity in governance requires transparency, accountability, and absence of conflict of interest",
        "Institutional mechanisms and personal ethics both matter",
    ],
    "good_to_have_points": [
        "Probity goes beyond minimum legal compliance",
        "Citizen trust is a major outcome of probity",
        "Codes, audits, and disclosures support ethical governance",
    ],
    "extra_edge_points": [
        "Ethical culture is sustained by norms, incentives, and leadership signals",
        "Probity is preventive, not merely punitive",
    ],
    "core_facts": [
        "Probity differs from mere procedural legality",
        "Conflict of interest can be real, potential, or perceived",
        "Integrity systems reduce discretion abuse and trust deficit",
    ],
    "classification": [{"title": "Pillars", "items": ["Integrity", "Transparency", "Accountability", "Fairness", "Impartiality"]}],
    "case_laws": [],
    "current_affairs_seed": [
        {
            "issue": "Debates around transparency in appointments, procurement, and public disclosure",
            "explanation": "Current governance debates repeatedly return to ethics, transparency, and trust.",
            "static_linkage": "Connect with probity, conflict of interest, and institutional integrity.",
            "upsc_relevance": "Directly relevant for GS4 theory and case studies.",
        }
    ],
    "mains_frame": {
        "intro": ["Define probity as ethical integrity in public decision-making."],
        "body": ["Explain dimensions", "Show institutional mechanisms", "Add examples"],
        "conclusion": ["Conclude that probity preserves democratic trust and administrative legitimacy."],
    },
    "value_addition": ["Conflict of interest matrix", "Ethical infrastructure", "Trust-based governance"],
    "pyq": ["What do you understand by probity in governance?", "How can institutions strengthen ethical governance?"],
}


UPSC_SUBJECTS = [
    {
        "id": "sub_upsc_polity",
        "code": "GS2_POLITY",
        "key": "polity",
        "name": "Polity",
        "description": "Constitution, institutions, governance, and federal issues.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="polity", name="Historical Background", description="Evolution of constitutional and political institutions before the Constitution.", subtopics=["Company rule", "British Acts", "National movement influence"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Making of Constitution", description="Constituent Assembly, debates, committees, and adoption of the Constitution.", subtopics=["Constituent Assembly", "Drafting Committee", "Adoption process"], difficulty="easy", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Salient Features of Constitution", description="Core principles and institutional design of the Indian Constitution.", subtopics=["Parliamentary system", "Federal features", "Independent judiciary"], difficulty="easy", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Preamble", description="Philosophy and interpretive value of the Preamble.", subtopics=["Justice", "Liberty", "Equality", "Fraternity"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Citizenship", description="Citizenship provisions, amendments, and debates on belonging.", subtopics=["Constitutional provisions", "Citizenship Act", "Contemporary debates"], difficulty="medium", estimated_minutes=45),
            _make_topic(
                exam_code="UPSC",
                subject_key="polity",
                name="Fundamental Rights",
                description="Constitutional rights, restrictions, judicial protection, and liberty-state balance.",
                subtopics=["Right to Equality", "Freedom and liberty", "Constitutional remedies", "Judicial expansion"],
                difficulty="medium",
                estimated_minutes=55,
                explicit_id="topic_upsc_polity_fundamental_rights",
                learning_objectives=[
                    "Explain the scope and significance of Part III.",
                    "Differentiate reasonable restrictions from core guarantees.",
                    "Use landmark judgments in mains answers.",
                ],
                knowledge=FUNDAMENTAL_RIGHTS_KNOWLEDGE,
            ),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Directive Principles of State Policy", description="Directive Principles, welfare state goals, and governance implications.", subtopics=["Socialist principles", "Gandhian principles", "Liberal-intellectual principles"], difficulty="medium", estimated_minutes=50, explicit_id="topic_upsc_polity_dpsp"),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Fundamental Duties", description="Constitutional duties, civic culture, and constitutional morality.", subtopics=["Constitutional status", "Scope", "Enforcement debates"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Union Executive", description="President, Vice-President, Prime Minister, and Council of Ministers.", subtopics=["President", "Prime Minister", "Council of Ministers"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Parliament", description="Structure, legislative procedure, financial control, and accountability of Parliament.", subtopics=["Lok Sabha", "Rajya Sabha", "Committees", "Legislative oversight"], difficulty="medium", estimated_minutes=50, explicit_id="topic_upsc_polity_parliament_accountability"),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Judiciary", description="Supreme Court, judicial review, and constitutional adjudication.", subtopics=["Supreme Court", "High Courts", "Judicial review", "Judicial appointments"], difficulty="hard", estimated_minutes=55),
            _make_topic(
                exam_code="UPSC",
                subject_key="polity",
                name="Federalism and Cooperative Federalism",
                description="Union-state relations, asymmetry, fiscal federalism, and cooperative mechanisms.",
                subtopics=["Legislative relations", "Fiscal federalism", "Intergovernmental bodies", "Current tensions"],
                difficulty="hard",
                estimated_minutes=55,
                explicit_id="topic_upsc_polity_federalism",
                learning_objectives=[
                    "Differentiate administrative, legislative, and fiscal federal issues.",
                    "Explain cooperative and competitive federalism.",
                    "Use contemporary issues to evaluate federal tensions.",
                ],
                knowledge=FEDERALISM_KNOWLEDGE,
            ),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Local Government", description="Panchayati Raj, urban local bodies, and decentralization.", subtopics=["73rd Amendment", "74th Amendment", "Devolution"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Constitutional Bodies", description="Constitutional institutions and their role in democratic governance.", subtopics=["Election Commission", "Finance Commission", "CAG", "UPSC"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Non-Constitutional Bodies", description="Statutory and non-statutory bodies involved in governance and oversight.", subtopics=["NITI Aayog", "NHRC", "CIC"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Amendment of Constitution", description="Procedure, flexibility-rigidity balance, and judicial limits on amendment power.", subtopics=["Article 368", "Basic structure doctrine", "Amendment trends"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Emergency Provisions", description="National, state, and financial emergencies and their constitutional implications.", subtopics=["National emergency", "President's Rule", "Financial emergency"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="polity", name="Elections and Representation", description="Electoral system, representation, and reform debates in democracy.", subtopics=["Representation of the People", "Delimitation", "Electoral reforms"], difficulty="medium", estimated_minutes=45),
        ],
    },
    {
        "id": "sub_upsc_economy",
        "code": "GS3_ECONOMY",
        "key": "economy",
        "name": "Economy",
        "description": "Macro-economy, agriculture, public finance, and inclusive growth.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="economy", name="National Income", description="Measurement, aggregates, and limitations of national income accounting.", subtopics=["GDP and GNP", "Nominal vs real", "Measurement issues"], difficulty="easy", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Growth and Development", description="Growth, development, and structural transformation in the Indian economy.", subtopics=["Growth vs development", "Human development", "Structural change"], difficulty="easy", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Poverty and Unemployment", description="Nature, measurement, and policy response to poverty and unemployment.", subtopics=["Poverty estimates", "Jobless growth", "Welfare schemes"], difficulty="medium", estimated_minutes=45),
            _make_topic(
                exam_code="UPSC",
                subject_key="economy",
                name="Inflation and Monetary Policy",
                description="Causes, consequences, and policy management of inflation in India.",
                subtopics=["Demand-pull", "Cost-push", "Inflation targeting", "MPC"],
                difficulty="medium",
                estimated_minutes=50,
                explicit_id="topic_upsc_economy_inflation",
                learning_objectives=[
                    "Distinguish key types of inflation.",
                    "Explain inflation’s welfare and growth effects.",
                    "Link inflation trends to monetary policy.",
                ],
                knowledge=INFLATION_KNOWLEDGE,
            ),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Banking and Financial Inclusion", description="Banking sector, credit transmission, and financial inclusion architecture.", subtopics=["Banking structure", "Financial inclusion", "NPA and reforms"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Fiscal Policy and Budget", description="Budgeting, deficit choices, and fiscal management in India.", subtopics=["Budget process", "Subsidies", "Fiscal consolidation"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Taxation and GST", description="Direct and indirect taxes, GST design, and fiscal federalism.", subtopics=["Direct taxes", "Indirect taxes", "GST Council"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="External Sector and Balance of Payments", description="Trade, capital flows, exchange rates, and external stability.", subtopics=["Current account", "Capital account", "Exchange rate"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Infrastructure", description="Infrastructure gaps, financing, and growth multiplier effects.", subtopics=["Transport", "Power", "Logistics"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Agriculture and Food Security", description="Farm productivity, food systems, and nutritional security.", subtopics=["Agricultural productivity", "Food systems", "Nutrition"], difficulty="medium", estimated_minutes=45),
            _make_topic(
                exam_code="UPSC",
                subject_key="economy",
                name="MSP, Procurement, and Food Security",
                description="Minimum support price, procurement incentives, and food system outcomes.",
                subtopics=["MSP", "Procurement", "PDS", "Reform options"],
                difficulty="medium",
                estimated_minutes=45,
                explicit_id="topic_upsc_economy_msp",
                learning_objectives=[
                    "Explain the rationale behind MSP.",
                    "Assess procurement and food security linkages.",
                    "Discuss distortions and reforms.",
                ],
                knowledge=MSP_KNOWLEDGE,
            ),
            _make_topic(
                exam_code="UPSC",
                subject_key="economy",
                name="Fiscal Deficit and Public Investment",
                description="Deficit management, quality of expenditure, and growth-stability balance.",
                subtopics=["FRBM", "Capital expenditure", "Debt sustainability"],
                difficulty="medium",
                estimated_minutes=45,
                explicit_id="topic_upsc_economy_fiscal_deficit",
                learning_objectives=[
                    "Define fiscal deficit precisely.",
                    "Differentiate productive and unproductive borrowing.",
                    "Link capital expenditure with growth quality.",
                ],
                knowledge=FISCAL_DEFICIT_KNOWLEDGE,
            ),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Inclusive Growth", description="Inclusion, welfare delivery, and regionally balanced development.", subtopics=["Inclusion", "Social sector", "Regional inequality"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="economy", name="Employment and Skilling", description="Labour markets, skilling, and quality of employment.", subtopics=["Labour market", "Skilling", "Formalization"], difficulty="medium", estimated_minutes=40),
        ],
    },
    {
        "id": "sub_upsc_geography",
        "code": "GS1_GEOGRAPHY",
        "key": "geography",
        "name": "Geography",
        "description": "Physical, Indian, human, and environmental geography.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="geography", name="Geomorphology", description="Landforms, earth processes, and geomorphic cycles.", subtopics=["Interior of Earth", "Volcanism", "Plate tectonics"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Climatology", description="Atmosphere, pressure systems, and climatic patterns.", subtopics=["Atmosphere", "Winds", "Climate types"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Oceanography", description="Ocean currents, marine resources, and ocean dynamics.", subtopics=["Ocean floor", "Currents", "Marine resources"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Indian Physical Geography", description="Relief, physiography, and regional divisions of India.", subtopics=["Himalayas", "Peninsular plateau", "Coastal plains"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="geography", name="River Systems", description="Drainage patterns, river basins, and water issues.", subtopics=["Himalayan rivers", "Peninsular rivers", "Interlinking debates"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Soil and Natural Vegetation", description="Soil profiles, natural vegetation, and ecosystem zones.", subtopics=["Soil types", "Vegetation regions", "Soil degradation"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Agriculture Geography", description="Cropping patterns, agro-climatic zones, and farm systems.", subtopics=["Cropping pattern", "Agro-climatic zones", "Irrigation"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Resources and Industries", description="Distribution of resources and industrial location factors.", subtopics=["Minerals", "Energy resources", "Industrial regions"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Population and Settlement", description="Population dynamics, migration, and settlement geography.", subtopics=["Demography", "Migration", "Urban settlement"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Disaster Management", description="Natural hazards, vulnerability, and disaster resilience.", subtopics=["Earthquakes", "Floods", "Preparedness"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="Human Geography", description="Economic and social organization of human space.", subtopics=["Human development", "Economic geography", "Cultural regions"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="geography", name="World Geography", description="Continents, resources, and major global geographic patterns.", subtopics=["Continents", "Resource regions", "Geopolitical geography"], difficulty="medium", estimated_minutes=45),
        ],
    },
    {
        "id": "sub_upsc_history",
        "code": "GS1_HISTORY",
        "key": "history",
        "name": "History",
        "description": "Ancient, medieval, modern, post-independence, and world history.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="history", name="Ancient India", description="Sources, society, and state formation in ancient India.", subtopics=["Indus Valley", "Vedic Age", "Mahajanapadas"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Buddhism and Jainism", description="Rise, teachings, and social impact of Buddhism and Jainism.", subtopics=["Teachings", "Councils", "Social context"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="history", name="Mauryan and Gupta Period", description="Imperial formations, administration, and cultural developments.", subtopics=["Mauryan administration", "Ashoka", "Gupta achievements"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Medieval India", description="Political structures, society, and culture in medieval India.", subtopics=["Delhi Sultanate", "Regional kingdoms", "Society"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Bhakti and Sufi Movements", description="Religious reform, syncretism, and social change.", subtopics=["Bhakti saints", "Sufi orders", "Social impact"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="history", name="Mughal Administration", description="Institutions, economy, and governance under the Mughals.", subtopics=["Mansabdari", "Revenue system", "Imperial culture"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Advent of Europeans", description="European trading companies and colonial expansion.", subtopics=["Portuguese", "French", "British"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="history", name="Revolt of 1857", description="Causes, course, and interpretations of the revolt.", subtopics=["Causes", "Spread", "Consequences"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Socio-Religious Reform Movements", description="Reform initiatives and intellectual currents in colonial India.", subtopics=["Brahmo Samaj", "Arya Samaj", "Aligarh movement"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Moderates and Extremists", description="Early nationalist politics and ideological evolution.", subtopics=["Moderate phase", "Extremist phase", "Methods and ideas"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Gandhian Phase", description="Mass movements and political strategy under Gandhi.", subtopics=["Non-cooperation", "Civil Disobedience", "Quit India"], difficulty="medium", estimated_minutes=50),
            _make_topic(exam_code="UPSC", subject_key="history", name="Constitutional Developments", description="Constitutional reforms and negotiations before independence.", subtopics=["Acts and reforms", "Round Table Conferences", "Cabinet Mission"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Post-Independence India", description="Nation-building, integration, and state reorganization after 1947.", subtopics=["Integration of states", "Reorganization", "Institution-building"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="World History", description="Revolutions, industrialization, and global political transformations.", subtopics=["French Revolution", "Industrial Revolution", "World Wars"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="history", name="Art and Culture", description="Architecture, painting, performing arts, and cultural traditions.", subtopics=["Architecture", "Music and dance", "Literature"], difficulty="medium", estimated_minutes=45),
        ],
    },
    {
        "id": "sub_upsc_environment",
        "code": "GS3_ENVIRONMENT",
        "key": "environment",
        "name": "Environment",
        "description": "Ecology, biodiversity, climate, and environmental governance.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="environment", name="Ecology", description="Ecosystems, ecological principles, and energy flows.", subtopics=["Ecosystems", "Food chains", "Ecological succession"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Biodiversity", description="Levels, values, and threats to biodiversity.", subtopics=["Genetic diversity", "Species diversity", "Biodiversity loss"], difficulty="easy", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Climate Change", description="Drivers, impacts, adaptation, and mitigation in climate governance.", subtopics=["GHG emissions", "Adaptation", "Mitigation"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Environmental Pollution", description="Air, water, soil, and noise pollution with control strategies.", subtopics=["Air pollution", "Water pollution", "Waste management"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Conservation Initiatives", description="Conservation strategies, institutions, and community participation.", subtopics=["In-situ conservation", "Ex-situ conservation", "Community efforts"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Protected Areas", description="National parks, sanctuaries, biosphere reserves, and conservation planning.", subtopics=["National parks", "Sanctuaries", "Biosphere reserves"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Environmental Impact Assessment", description="EIA process, regulation, and sustainability screening.", subtopics=["EIA process", "Clearance regime", "Public consultation"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="environment", name="International Environmental Agreements", description="Global conventions and climate negotiations.", subtopics=["UNFCCC", "CBD", "Montreal Protocol"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Disaster and Environment", description="Environmental dimensions of disasters and resilience planning.", subtopics=["Vulnerability", "Climate disasters", "Ecosystem resilience"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Sustainable Development", description="Development pathways that balance economy, society, and environment.", subtopics=["SDGs", "Circular economy", "Sustainability indicators"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="environment", name="Environmental Laws", description="Key legal instruments and institutional framework for environmental governance.", subtopics=["EPA 1986", "Forest laws", "Wildlife laws"], difficulty="medium", estimated_minutes=45),
        ],
    },
    {
        "id": "sub_upsc_science_tech",
        "code": "GS3_SCIENCE_TECH",
        "key": "science_tech",
        "name": "Science & Tech",
        "description": "Emerging technologies, innovation, and science applications.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Basics of Science in Everyday Life", description="Fundamental science concepts with applications in daily life and policy.", subtopics=["Everyday science", "Public health", "Applied science"], difficulty="easy", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Space Technology", description="Space missions, satellite applications, and strategic significance.", subtopics=["Launch vehicles", "Satellite applications", "Space policy"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Biotechnology", description="Biotech applications in health, agriculture, and industry.", subtopics=["Genetic engineering", "Vaccines", "Agricultural biotech"], difficulty="medium", estimated_minutes=45),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="ICT and Digital Infrastructure", description="Digital public infrastructure, connectivity, and digital governance.", subtopics=["Digital public goods", "5G", "Digital inclusion"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Cybersecurity", description="Cyber threats, resilience, and regulatory response.", subtopics=["Cyber threats", "Data security", "Cyber governance"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Artificial Intelligence", description="AI applications, governance, and ethics.", subtopics=["Machine learning", "Use cases", "AI governance"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Robotics and Automation", description="Automation, robotics, and labour-market implications.", subtopics=["Industrial robotics", "Automation", "Future of work"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Nanotechnology and Materials", description="Advanced materials, nanotechnology, and industrial applications.", subtopics=["Nanomaterials", "Applications", "Safety"], difficulty="medium", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Health Technology", description="Medical technology, diagnostics, and public health systems.", subtopics=["Telemedicine", "Diagnostics", "Medical devices"], difficulty="medium", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Defence Technology", description="Strategic technology, indigenization, and defence preparedness.", subtopics=["Missile systems", "Naval technology", "Atmanirbhar defence"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Energy Technology", description="Energy systems, transition technologies, and strategic autonomy.", subtopics=["Renewables", "Storage", "Hydrogen"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="science_tech", name="Innovation and Intellectual Property", description="Innovation ecosystems, patents, and research translation.", subtopics=["Start-up ecosystem", "IPR", "Research funding"], difficulty="easy", estimated_minutes=35),
        ],
    },
    {
        "id": "sub_upsc_ethics",
        "code": "GS4_ETHICS",
        "key": "ethics",
        "name": "Ethics",
        "description": "Ethics theory, public service values, and case-study practice.",
        "topics": [
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Ethics and Human Interface", description="Nature, dimensions, and determinants of ethics in human conduct.", subtopics=["Ethics", "Values", "Determinants of conduct"], difficulty="easy", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Human Values", description="Family, society, and educational sources of values.", subtopics=["Sources of values", "Value conflict", "Socialization"], difficulty="easy", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Attitude", description="Attitude, behaviour, and moral orientation in public life.", subtopics=["Components of attitude", "Moral attitude", "Behavioural change"], difficulty="easy", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Aptitude and Foundational Values", description="Integrity, impartiality, objectivity, and civil-service orientation.", subtopics=["Integrity", "Objectivity", "Impartiality"], difficulty="medium", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Emotional Intelligence", description="Emotional awareness, regulation, and ethical leadership.", subtopics=["Self-awareness", "Empathy", "Leadership"], difficulty="easy", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Moral Thinkers", description="Ideas of moral thinkers and their relevance to governance.", subtopics=["Indian thinkers", "Western thinkers", "Applied ethics"], difficulty="medium", estimated_minutes=40),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Public Service Values", description="Ethics of public administration and citizen-centric service.", subtopics=["Public service", "Citizen centricity", "Responsibility"], difficulty="medium", estimated_minutes=35),
            _make_topic(
                exam_code="UPSC",
                subject_key="ethics",
                name="Probity in Governance",
                description="Integrity, transparency, accountability, and ethical standards in public office.",
                subtopics=["Integrity", "Transparency", "Conflict of interest", "Institutional safeguards"],
                difficulty="medium",
                estimated_minutes=40,
                explicit_id="topic_upsc_ethics_probity",
                learning_objectives=[
                    "Define probity and distinguish it from legality.",
                    "Apply probity to institutions and public service.",
                    "Use examples in ethics answers.",
                ],
                knowledge=PROBITY_KNOWLEDGE,
            ),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Accountability and Transparency", description="Accountability systems, openness, and ethical governance.", subtopics=["Transparency", "Audit", "RTI", "Accountability"], difficulty="medium", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Ethics in Governance", description="Ethical dilemmas, corruption control, and institutional ethics.", subtopics=["Corruption", "Ethical dilemmas", "Institutional reforms"], difficulty="medium", estimated_minutes=35),
            _make_topic(exam_code="UPSC", subject_key="ethics", name="Case Study Approach", description="Structured method for solving ethics case studies.", subtopics=["Stakeholder mapping", "Options analysis", "Ethical justification"], difficulty="medium", estimated_minutes=40),
        ],
    },
]


SSC_SUBJECTS = [
    {
        "id": "sub_ssc_quant",
        "code": "SSC_QUANT",
        "key": "quant",
        "name": "Quantitative Aptitude",
        "description": "Arithmetic, algebra, geometry, and data interpretation.",
        "topics": [
            _make_topic(exam_code="SSC", subject_key="quant", name="Number System", description="Basic arithmetic properties and operations.", subtopics=["Divisibility", "LCM and HCF", "Remainders"], difficulty="easy", estimated_minutes=25),
            _make_topic(exam_code="SSC", subject_key="quant", name="Percentage and Profit-Loss", description="Percentage applications, gain-loss, and discount.", subtopics=["Percentages", "Profit and loss", "Discount"], difficulty="easy", estimated_minutes=25),
            _make_topic(exam_code="SSC", subject_key="quant", name="Ratio, Proportion, and Mixture", description="Proportional reasoning and mixture problems.", subtopics=["Ratio", "Proportion", "Mixture and allegation"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="SSC", subject_key="quant", name="Time, Speed, and Distance", description="Motion problems and relative speed.", subtopics=["Average speed", "Relative speed", "Boats and streams"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="SSC", subject_key="quant", name="Geometry and Mensuration", description="Plane geometry and measurement formulas.", subtopics=["Triangles", "Circles", "Mensuration"], difficulty="medium", estimated_minutes=25),
        ],
    },
    {
        "id": "sub_ssc_reasoning",
        "code": "SSC_REASONING",
        "key": "reasoning",
        "name": "General Intelligence",
        "description": "Verbal and non-verbal reasoning for SSC exams.",
        "topics": [
            _make_topic(exam_code="SSC", subject_key="reasoning", name="Analogy and Classification", description="Pattern recognition and classification questions.", subtopics=["Analogy", "Classification", "Odd one out"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="reasoning", name="Series and Coding-Decoding", description="Series, coding-decoding, and pattern-based logic.", subtopics=["Number series", "Letter series", "Coding-decoding"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="reasoning", name="Blood Relations and Direction Sense", description="Relationship and direction-based logic questions.", subtopics=["Blood relations", "Direction sense", "Ordering"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="reasoning", name="Syllogism and Statement Logic", description="Deduction, logical consistency, and statement-based reasoning.", subtopics=["Syllogism", "Statements", "Conclusions"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="reasoning", name="Puzzles and Seating Arrangement", description="Arrangement and puzzle-based reasoning.", subtopics=["Linear arrangement", "Circular arrangement", "Simple puzzles"], difficulty="medium", estimated_minutes=25),
        ],
    },
    {
        "id": "sub_ssc_english",
        "code": "SSC_ENGLISH",
        "key": "english",
        "name": "English",
        "description": "Grammar, vocabulary, and comprehension.",
        "topics": [
            _make_topic(exam_code="SSC", subject_key="english", name="Grammar Basics", description="Parts of speech and foundational grammar.", subtopics=["Nouns and pronouns", "Verbs", "Adjectives"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="english", name="Error Spotting", description="Sentence errors and grammatical correction.", subtopics=["Subject-verb agreement", "Tense", "Prepositions"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="english", name="Vocabulary", description="Synonyms, antonyms, and one-word substitutions.", subtopics=["Synonyms", "Antonyms", "Idioms"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="english", name="Reading Comprehension", description="Passage-based comprehension and inference.", subtopics=["Main idea", "Inference", "Vocabulary in context"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="english", name="Cloze Test and Fillers", description="Contextual language use through cloze and fillers.", subtopics=["Cloze test", "Fillers", "Sentence improvement"], difficulty="medium", estimated_minutes=20),
        ],
    },
    {
        "id": "sub_ssc_awareness",
        "code": "SSC_AWARENESS",
        "key": "awareness",
        "name": "General Awareness",
        "description": "Static GK, current affairs, and science basics.",
        "topics": [
            _make_topic(exam_code="SSC", subject_key="awareness", name="History and Culture", description="Important historical facts and cultural awareness.", subtopics=["Ancient history", "Modern history", "Culture"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="awareness", name="Polity and Constitution", description="Basic constitution and political facts for objective exams.", subtopics=["Constitution basics", "Parliament", "President"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="awareness", name="Geography and Environment", description="Indian geography and environmental basics.", subtopics=["Physical geography", "Indian geography", "Environment"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="awareness", name="Economy and Government Schemes", description="Economy basics and important schemes.", subtopics=["Economy basics", "Budget", "Schemes"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="SSC", subject_key="awareness", name="Science Basics", description="Physics, chemistry, and biology basics for SSC.", subtopics=["Physics", "Chemistry", "Biology"], difficulty="easy", estimated_minutes=20),
        ],
    },
]


BANKING_SUBJECTS = [
    {
        "id": "sub_banking_reasoning",
        "code": "BANK_REASONING",
        "key": "reasoning",
        "name": "Reasoning Ability",
        "description": "Banking exam reasoning and puzzles.",
        "topics": [
            _make_topic(exam_code="BANKING", subject_key="reasoning", name="Seating Arrangement", description="Linear and circular seating arrangement.", subtopics=["Linear", "Circular", "Complex arrangement"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="BANKING", subject_key="reasoning", name="Puzzles", description="Floor, box, and scheduling puzzles.", subtopics=["Floor puzzle", "Box puzzle", "Scheduling"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="BANKING", subject_key="reasoning", name="Syllogism", description="Logical deduction and statement-based reasoning.", subtopics=["Basic syllogism", "New pattern", "Venn logic"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="reasoning", name="Input-Output", description="Pattern rearrangement and logic sequencing.", subtopics=["Word arrangement", "Number arrangement", "Mixed arrangement"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="reasoning", name="Data Sufficiency", description="Sufficiency-based reasoning questions.", subtopics=["Two statements", "Case-based sufficiency", "Elimination"], difficulty="medium", estimated_minutes=20),
        ],
    },
    {
        "id": "sub_banking_quant",
        "code": "BANK_QUANT",
        "key": "quant",
        "name": "Quantitative Aptitude",
        "description": "Arithmetic and data interpretation for banking exams.",
        "topics": [
            _make_topic(exam_code="BANKING", subject_key="quant", name="Simplification and Approximation", description="Fast arithmetic and approximation.", subtopics=["BODMAS", "Approximation", "Speed maths"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="quant", name="Data Interpretation", description="Table, line, and case-based DI.", subtopics=["Table DI", "Line graph", "Caselet DI"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="BANKING", subject_key="quant", name="Quadratic Equations", description="Equation comparison and roots.", subtopics=["Roots", "Comparison", "Factorization"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="quant", name="Arithmetic", description="Core arithmetic for speed and accuracy.", subtopics=["Percentage", "Ratio", "Profit and loss"], difficulty="medium", estimated_minutes=25),
            _make_topic(exam_code="BANKING", subject_key="quant", name="Number Series", description="Missing and wrong number series.", subtopics=["Missing number", "Wrong number", "Pattern spotting"], difficulty="easy", estimated_minutes=20),
        ],
    },
    {
        "id": "sub_banking_english",
        "code": "BANK_ENGLISH",
        "key": "english",
        "name": "English Language",
        "description": "Comprehension, grammar, and usage for banking exams.",
        "topics": [
            _make_topic(exam_code="BANKING", subject_key="english", name="Reading Comprehension", description="Banking passage comprehension.", subtopics=["Inference", "Vocabulary", "Main idea"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="english", name="Error Detection", description="Grammar-based error detection.", subtopics=["Grammar", "Usage", "Sentence correction"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="english", name="Cloze Test", description="Contextual fillers and cloze practice.", subtopics=["Cloze logic", "Vocabulary", "Grammar"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="english", name="Para Jumbles", description="Sentence ordering and coherence.", subtopics=["Sentence sequence", "Coherence", "Connectors"], difficulty="medium", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="english", name="Vocabulary and Usage", description="Phrase replacement and vocabulary usage.", subtopics=["Phrases", "Word usage", "Idioms"], difficulty="easy", estimated_minutes=20),
        ],
    },
    {
        "id": "sub_banking_awareness",
        "code": "BANK_AWARENESS",
        "key": "awareness",
        "name": "Banking Awareness",
        "description": "Banking, finance, and economic awareness.",
        "topics": [
            _make_topic(exam_code="BANKING", subject_key="awareness", name="Banking System", description="Structure and functions of the banking system.", subtopics=["RBI", "Commercial banks", "NBFC"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="awareness", name="Monetary Policy", description="Policy instruments and RBI decisions.", subtopics=["Repo", "CRR", "SLR"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="awareness", name="Financial Markets", description="Money market, capital market, and instruments.", subtopics=["Money market", "Capital market", "Instruments"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="awareness", name="Government Schemes", description="Schemes relevant to finance and inclusion.", subtopics=["Financial inclusion", "Insurance", "Credit"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="awareness", name="Current Financial Affairs", description="Recent policy, regulatory, and banking updates.", subtopics=["Policy updates", "Mergers", "Rates and reports"], difficulty="easy", estimated_minutes=20),
        ],
    },
    {
        "id": "sub_banking_computer",
        "code": "BANK_COMPUTER",
        "key": "computer",
        "name": "Computer Aptitude",
        "description": "Computer fundamentals and digital systems.",
        "topics": [
            _make_topic(exam_code="BANKING", subject_key="computer", name="Computer Basics", description="Core computer terminology and concepts.", subtopics=["Hardware", "Software", "Operating systems"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="computer", name="Internet and Networking", description="Internet basics and networking concepts.", subtopics=["Internet", "Networking", "Protocols"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="computer", name="MS Office and Productivity", description="Basic office software and productivity tools.", subtopics=["Word", "Excel", "PowerPoint"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="computer", name="Cyber Safety", description="Security basics and safe digital behaviour.", subtopics=["Passwords", "Phishing", "Safe browsing"], difficulty="easy", estimated_minutes=20),
            _make_topic(exam_code="BANKING", subject_key="computer", name="Digital Payments", description="Digital banking and payment systems.", subtopics=["UPI", "Cards", "NEFT and RTGS"], difficulty="easy", estimated_minutes=20),
        ],
    },
]


def _subject_payload(*, exam_id: str, code: str, key: str, name: str, description: str, display_order: int, topics: list[dict]) -> dict:
    return {
        "id": f"sub_{exam_id.replace('exam_', '')}_{key}",
        "code": code,
        "name": name,
        "description": description,
        "display_order": display_order,
        "topics": topics,
    }


SEED_CATALOG = [
    {
        "id": "exam_upsc",
        "code": "UPSC",
        "name": "UPSC Civil Services",
        "description": "A syllabus-driven UPSC preparation workspace with deterministic evaluation, notes, MCQs, flashcards, and revision.",
        "subjects": [
            _subject_payload(exam_id="exam_upsc", code=subject["code"], key=subject["key"], name=subject["name"], description=subject["description"], display_order=index, topics=subject["topics"])
            for index, subject in enumerate(UPSC_SUBJECTS, start=1)
        ],
    },
    {
        "id": "exam_ssc",
        "code": "SSC",
        "name": "SSC CGL",
        "description": "An exam-aware workspace for SSC aptitude, reasoning, English, and awareness practice.",
        "subjects": [
            _subject_payload(exam_id="exam_ssc", code=subject["code"], key=subject["key"], name=subject["name"], description=subject["description"], display_order=index, topics=subject["topics"])
            for index, subject in enumerate(SSC_SUBJECTS, start=1)
        ],
    },
    {
        "id": "exam_banking",
        "code": "BANKING",
        "name": "Banking Exams",
        "description": "A clean banking-exam workspace focused on MCQ practice, topic revision, and exam-aware navigation.",
        "subjects": [
            _subject_payload(exam_id="exam_banking", code=subject["code"], key=subject["key"], name=subject["name"], description=subject["description"], display_order=index, topics=subject["topics"])
            for index, subject in enumerate(BANKING_SUBJECTS, start=1)
        ],
    },
]


def build_product_note(topic: dict) -> dict:
    subtopics = topic.get("subtopics", [])
    knowledge = topic.get("knowledge", {})
    framework = subtopics[:5] or knowledge.get("must_have_points", [])[:5] or [topic["name"]]
    key_anchors = (
        knowledge.get("core_facts", [])[:2]
        + knowledge.get("case_laws", [])[:2]
        + knowledge.get("value_addition", [])[:2]
    ) or [f"{topic['name']} core anchor"]
    pyq_links = knowledge.get("pyq", [])[:2] or [f"Review previous-year framing on {topic['name']}."]
    linkages = [
        f"Connect {topic['name']} to governance and policy outcomes.",
        f"Link {topic['name']} with current affairs debates for GS enrichment.",
    ]
    return {
        "core_idea": topic["description"],
        "framework": framework,
        "key_anchors": key_anchors[:6],
        "answer_direction": [
            "Start with demand-aligned core idea in one line.",
            "Use 3-5 framework dimensions as body headings.",
            "Close with one reform-oriented or evaluative linkage.",
        ],
        "linkages": linkages + pyq_links,
    }


def build_seed_questions(exam: dict, subject: dict, topic: dict) -> list[dict]:
    subtopics = topic.get("subtopics", [])
    mcqs: list[dict] = []
    for index in range(5):
        focus = subtopics[index % len(subtopics)] if subtopics else topic["name"]
        mcqs.append(
            {
                "id": _question_id(topic["id"], "mcq", index + 1),
                "type": "mcq",
                "prompt": f"{topic['name']}: pick the most accurate statement about {focus}.",
                "options": [
                    {"id": "A", "text": f"{focus} is unrelated to the larger theme of {topic['name']}."},
                    {"id": "B", "text": f"{focus} is an important exam-relevant dimension of {topic['name']}."},
                    {"id": "C", "text": f"{focus} can only be studied in isolation from the syllabus."},
                    {"id": "D", "text": f"{focus} is not useful for revision or practice."},
                ],
                "correct_option_id": "B",
                "explanation": f"{focus} is a meaningful, exam-relevant part of {topic['name']}.",
                "explanation_hint": "Choose the balanced and syllabus-aligned statement.",
                "difficulty": topic["difficulty"],
                "metadata": {
                    "seed_source": STUDY_SEED_SOURCE,
                    "kind": "mcq",
                    "exam_code": exam["code"],
                    "subject_name": subject["name"],
                    "topic_name": topic["name"],
                },
            }
        )

    if exam["code"] != "UPSC":
        return mcqs

    practice_prompt = {
        "id": _question_id(topic["id"], "practice", 1),
        "type": "mains",
        "prompt": f"Discuss {topic['name']} with conceptual clarity, structure, and one relevant example.",
        "options": None,
        "correct_option_id": None,
        "explanation": f"A good answer on {topic['name']} should define the topic, cover its dimensions, and conclude with relevance.",
        "explanation_hint": "Use intro, body, and conclusion with one concrete anchor.",
        "difficulty": topic["difficulty"],
        "metadata": {
            "seed_source": STUDY_SEED_SOURCE,
            "kind": "practice",
            "exam_code": exam["code"],
            "recommended_word_limit": 180,
        },
    }
    pyq_prompt = {
        "id": _question_id(topic["id"], "pyq", 1),
        "type": "mains",
        "prompt": (topic.get("knowledge", {}).get("pyq") or [f"Examine the significance of {topic['name']}."])[0],
        "options": None,
        "correct_option_id": None,
        "explanation": f"This prompt reflects the kind of framing used to test {topic['name']} in mains practice.",
        "explanation_hint": "Answer by defining the topic, analysing dimensions, and ending with significance.",
        "difficulty": topic["difficulty"],
        "metadata": {
            "seed_source": STUDY_SEED_SOURCE,
            "kind": "pyq",
            "exam_code": exam["code"],
            "recommended_word_limit": 180,
        },
    }
    return mcqs + [practice_prompt, pyq_prompt]
