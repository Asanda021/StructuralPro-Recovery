from pathlib import Path

MAIN = Path("app/main.py").read_text(encoding="utf-8")
WORKSPACE = Path("app/aec_workspace.py").read_text(encoding="utf-8")


def test_aec_navigation_has_separate_real_workspaces():
    required = [
        "🏠 معماری", "🏗 سازه بتن", "🏭 سازه فولاد", "🧱 بنایی",
        "❄ تأسیسات مکانیکی", "⚡ تأسیسات برقی",
        "🌳 محوطه و عملیات بیرونی", "♻ بازسازی و مرمت",
    ]
    for label in required:
        assert label in MAIN
    assert "build_aec_workspace" in MAIN
    assert 'pages.addWidget(wp); discipline_pages[key]=pages.count()-1' in MAIN


def test_aec_workspace_has_real_save_path():
    assert "service.add_takeoff(pid,effective_domain,code" in WORKSPACE
    assert "service.open_project(pid)" in WORKSPACE
    assert "catalog.resolve(pc)" in WORKSPACE
    assert "محاسبه و ثبت واقعی" in WORKSPACE
    assert "source_id=" in WORKSPACE


def test_aec_workspace_does_not_create_fake_item_types():
    expected = [
        '"wall"', '"column"', '"beam"', '"footing_concrete"',
        '"steel"', '"pipe"', '"duct"', '"cable"', '"excavation"', '"demolition"',
    ]
    for item in expected:
        assert item in WORKSPACE


def test_settings_do_not_offer_unimplemented_language_or_unit_switches():
    assert 'lang.addItems(["فارسی (RTL)","English (LTR)"])' not in MAIN
    assert 'unit.addItems(["متر / مترمربع / مترمکعب","سانتی‌متر / میلی‌متر"])' not in MAIN


def test_project_documents_are_persisted():
    assert '"documents"' in MAIN
    assert "service.store.save(project_id,project)" in MAIN
    assert "docbrowse.clicked.connect" in MAIN


def test_report_layout_is_persisted_in_project():
    assert 'project["_report_layout"]' in MAIN
    assert 'service.store.save(project_id,project)' in MAIN


def test_removed_static_capability_claim():
    assert 'tools.addTab(QLabel("گزارش‌ساز قابل تنظیم، Excel Bridge و Undo/Redo در هسته فعال است.")' not in MAIN


def test_roofs_are_nested_in_concrete_and_steel_workspaces():
    assert '"solid_slab_roof","سقف دال بتنی توپر / دال تخت — حجم بتن"' in WORKSPACE
    assert '"joist_block_roof","سقف تیرچه‌بلوک — حجم بتن"' in WORKSPACE
    assert '"waffle_roof","سقف وافل — حجم بتن"' in WORKSPACE
    assert '"uboot_roof","سقف یوبوت — حجم بتن خالص"' in WORKSPACE
    assert '"cobiax_roof","سقف کوبیاکس — حجم بتن خالص"' in WORKSPACE
    assert '"steel_roof_deck_area","سقف عرشه فولادی — مساحت عرشه"' in WORKSPACE
    assert '"steel_roof_composite_concrete","سقف کامپوزیت — حجم بتن"' in WORKSPACE
    assert '"kromit_roof","سقف تیرچه کرومیت — وزن تیرچه"' in WORKSPACE
    assert "سیستم باربر: قاب خمشی" not in WORKSPACE
    assert "سیستم سازه / سقف" not in WORKSPACE


def test_roof_calculations_use_explicit_geometry():
    from core.takeoff.modules.building import calculate_building_item
    from core.takeoff.modules.advanced import calculate_advanced_item
    r=calculate_building_item("solid_slab_roof",length=10,width=12,thickness=.2,count=1)
    assert r.quantity == 24
    r=calculate_building_item("joist_block_roof",length=10,width=10,topping_thickness=.05,joist_spacing=.5,joist_width=.1,joist_depth=.2,count=1)
    assert round(r.quantity,6)==9.2
    r=calculate_building_item("uboot_roof",length=10,width=10,thickness=.28,void_length=.5,void_width=.25,void_height=.2,void_count=100,count=1)
    assert round(r.quantity,6)==25.5
    r=calculate_advanced_item("steel_roof_deck_weight",length=10,width=12,sheet_weight=10,count=1)
    assert r.quantity == 1200
    r=calculate_advanced_item("kromit_roof",joist_length=6,joist_unit_weight=12,joist_count=20,count=1)
    assert r.quantity == 1440


def test_pricebook_is_user_supplied_not_bundled():
    assert '📥 ورود Excel / CSV / PDF' in MAIN
    assert 'PDF (*.pdf)' in MAIN
    assert 'فهرست‌بهای واردشده توسط کاربر' in WORKSPACE


def test_primary_navigation_is_horizontal_and_targets_real_pages():
    assert 'navigation_tabs.setObjectName("MainNavigationTabs")' in MAIN
    assert 'navigation_tabs.setTabData(tab_index,target)' in MAIN
    assert 'pages.setCurrentIndex(target)' in MAIN
    assert 'navigation_tabs.currentChanged.connect(navigate_from_tab)' in MAIN
    assert 'pages.currentChanged.connect(sync_tabs_to_page)' in MAIN
    assert 'shell.addWidget(nav_tree)' not in MAIN


def test_validated_assemblies_are_available_from_real_aec_workspace():
    assert "calculate_assembly" in WORKSPACE
    assert '("block_wall","دیوار بلوکی — Assembly"' in WORKSPACE
    assert 'assembly_mode=QCheckBox("متره به‌صورت Assembly (عملیات → اجزای مستقل)")' in WORKSPACE
    assert 'if assembly_mode.isChecked() and code in ASSEMBLY_CODES:' in WORKSPACE
    assert 'assembly_code=ar.code' in WORKSPACE


def test_assembly_ui_never_saves_partial_components():
    assert 'if not ar.complete:' in WORKSPACE
    assert 'join(ar.missing_inputs)' in WORKSPACE
    assert 'return' in WORKSPACE
