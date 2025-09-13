# Diagrama de flujo (Mermaid)

%%{init: {'flowchart': {'curve':'basis','nodeSpacing':60,'rankSpacing':90}, 'themeVariables': {'fontSize':'18px'}} }%%
```mermaid
flowchart TD
  subgraph carrito
    carrito__add_to_cart["_add_to_cart()"]
    carrito__build_ui["_build_ui()"]
    carrito__chg_qty["_chg_qty()"]
    carrito__db_path["_db_path()"]
    carrito__del_item["_del_item()"]
    carrito__ensure_tables["_ensure_tables()"]
    carrito__finalize_order["_finalize_order()"]
    carrito__go_back["_go_back()"]
    carrito__load_draft["_load_draft()"]
    carrito__persist_draft["_persist_draft()"]
    carrito__pick_product["_pick_product()"]
    carrito__price_to_int["_price_to_int()"]
    carrito__refresh_totals["_refresh_totals()"]
    carrito__render_cart["_render_cart()"]
    carrito__suggest["_suggest()"]
    carrito__sync_height["_sync_height()"]
    carrito__wrap_button["_wrap_button()"]
    carrito__wrap_label["_wrap_label()"]
    carrito_on_pre_enter["on_pre_enter()"]
  end
  subgraph DATASOURCES
    db_todoferre_db(["DB: todoferre.db"])
  end
  carrito__add_to_cart --> |<call>| carrito_<call>
  carrito__add_to_cart --> |_persist_draft| carrito__persist_draft
  carrito__add_to_cart --> |_render_cart| carrito__render_cart
  carrito__add_to_cart --> |int| carrito_int
  carrito__build_ui --> |<call>| carrito_<call>
  carrito__build_ui --> |_finalize_order| carrito__finalize_order
  carrito__build_ui --> |on_release| carrito__go_back
  carrito__build_ui --> |_suggest| carrito__suggest
  carrito__build_ui --> |add_widget| carrito_add_widget
  carrito__build_ui --> |clear_widgets| carrito_clear_widgets
  carrito__build_ui -.-> |BoxLayout| kivy_BoxLayout
  carrito__build_ui -.-> |Button| kivy_Button
  carrito__build_ui -.-> |GridLayout| kivy_GridLayout
  carrito__build_ui -.-> |Label| kivy_Label
  carrito__build_ui -.-> |ScrollView| kivy_ScrollView
  carrito__build_ui -.-> |TextInput| kivy_TextInput
  carrito__chg_qty --> |_persist_draft| carrito__persist_draft
  carrito__chg_qty --> |_render_cart| carrito__render_cart
  carrito__chg_qty --> |len| carrito_len
  carrito__chg_qty --> |max| carrito_max
  carrito__db_path --> |<call>| carrito_<call>
  carrito__del_item --> |<call>| carrito_<call>
  carrito__del_item --> |_persist_draft| carrito__persist_draft
  carrito__del_item --> |_render_cart| carrito__render_cart
  carrito__del_item --> |len| carrito_len
  carrito__ensure_tables --> |_db_path| carrito__db_path
  carrito__ensure_tables --> |close| carrito_close
  carrito__ensure_tables --> |commit| carrito_commit
  carrito__ensure_tables --> |cursor| carrito_cursor
  carrito__ensure_tables --> |execute| carrito_execute
  carrito__ensure_tables -.-> |connect| sqlite3_connect
  carrito__finalize_order --> |<call>| carrito_<call>
  carrito__finalize_order --> |_db_path| carrito__db_path
  carrito__finalize_order --> |_ensure_tables| carrito__ensure_tables
  carrito__finalize_order --> |close| carrito_close
  carrito__finalize_order --> |commit| carrito_commit
  carrito__finalize_order --> |count| carrito_count
  carrito__finalize_order --> |cursor| carrito_cursor
  carrito__finalize_order --> |execute| carrito_execute
  carrito__finalize_order --> |fetchone| carrito_fetchone
  carrito__finalize_order --> |int| carrito_int
  carrito__finalize_order --> |len| carrito_len
  carrito__finalize_order --> |print| carrito_print
  carrito__finalize_order --> |round| carrito_round
  carrito__finalize_order --> |sum| carrito_sum
  carrito__finalize_order -.-> |NoTransition| kivy_NoTransition
  carrito__finalize_order -.-> |randint| random_randint
  carrito__finalize_order -.-> |connect| sqlite3_connect
  carrito__finalize_order -.-> |time| time_time
  carrito__go_back -.-> |NoTransition| kivy_NoTransition
  carrito__load_draft --> |_build_ui| carrito__build_ui
  carrito__load_draft --> |_db_path| carrito__db_path
  carrito__load_draft --> |_render_cart| carrito__render_cart
  carrito__load_draft --> |close| carrito_close
  carrito__load_draft --> |cursor| carrito_cursor
  carrito__load_draft --> |execute| carrito_execute
  carrito__load_draft --> |fetchone| carrito_fetchone
  carrito__load_draft --> |get| carrito_get
  carrito__load_draft --> |int| carrito_int
  carrito__load_draft -.-> |loads| json_loads
  carrito__load_draft -.-> |connect| sqlite3_connect
  carrito__persist_draft --> |_db_path| carrito__db_path
  carrito__persist_draft --> |_ensure_tables| carrito__ensure_tables
  carrito__persist_draft --> |close| carrito_close
  carrito__persist_draft --> |commit| carrito_commit
  carrito__persist_draft --> |cursor| carrito_cursor
  carrito__persist_draft --> |execute| carrito_execute
  carrito__persist_draft --> |int| carrito_int
  carrito__persist_draft -.-> |dumps| json_dumps
  carrito__persist_draft -.-> |connect| sqlite3_connect
  carrito__persist_draft -.-> |time| time_time
  carrito__pick_product --> |_add_to_cart| carrito__add_to_cart
  carrito__price_to_int --> |int| carrito_int
  carrito__price_to_int --> |isinstance| carrito_isinstance
  carrito__price_to_int --> |str| carrito_str
  carrito__price_to_int -.-> |sub| re_sub
  carrito__refresh_totals --> |<call>| carrito_<call>
  carrito__refresh_totals --> |int| carrito_int
  carrito__refresh_totals --> |round| carrito_round
  carrito__refresh_totals --> |sum| carrito_sum
  carrito__render_cart --> |<call>| carrito_<call>
  carrito__render_cart --> |_chg_qty| carrito__chg_qty
  carrito__render_cart --> |_del_item| carrito__del_item
  carrito__render_cart --> |_refresh_totals| carrito__refresh_totals
  carrito__render_cart --> |_sync_height| carrito__sync_height
  carrito__render_cart --> |_wrap_label| carrito__wrap_label
  carrito__render_cart --> |add_widget| carrito_add_widget
  carrito__render_cart --> |bind| carrito_bind
  carrito__render_cart --> |enumerate| carrito_enumerate
  carrito__render_cart -.-> |BoxLayout| kivy_BoxLayout
  carrito__render_cart -.-> |Button| kivy_Button
  carrito__render_cart -.-> |dp| kivy_dp
  carrito__suggest --> |<call>| carrito_<call>
  carrito__suggest --> |_db_path| carrito__db_path
  carrito__suggest --> |_pick_product| carrito__pick_product
  carrito__suggest --> |_price_to_int| carrito__price_to_int
  carrito__suggest --> |_wrap_button| carrito__wrap_button
  carrito__suggest --> |close| carrito_close
  carrito__suggest --> |cursor| carrito_cursor
  carrito__suggest --> |execute| carrito_execute
  carrito__suggest --> |fetchall| carrito_fetchall
  carrito__suggest --> |len| carrito_len
  carrito__suggest -.-> |connect| sqlite3_connect
  carrito__sync_height --> |max| carrito_max
  carrito__sync_height -.-> |dp| kivy_dp
  carrito__wrap_button --> |bind| carrito_bind
  carrito__wrap_button --> |max| carrito_max
  carrito__wrap_button --> |on_release| carrito_on_release
  carrito__wrap_button --> |setattr| carrito_setattr
  carrito__wrap_button -.-> |Button| kivy_Button
  carrito__wrap_button -.-> |dp| kivy_dp
  carrito__wrap_label --> |bind| carrito_bind
  carrito__wrap_label --> |max| carrito_max
  carrito__wrap_label --> |setattr| carrito_setattr
  carrito__wrap_label -.-> |Label| kivy_Label
  carrito__wrap_label -.-> |dp| kivy_dp
  carrito_on_pre_enter --> |_build_ui| carrito__build_ui
  carrito_on_pre_enter --> |_ensure_tables| carrito__ensure_tables
  carrito_on_pre_enter --> |_load_draft| carrito__load_draft
  carrito_on_pre_enter --> |_refresh_totals| carrito__refresh_totals
  carrito_on_pre_enter --> |get| carrito_get
  carrito_on_pre_enter --> |getattr| carrito_getattr
  carrito_on_pre_enter -.-> |get_running_app| kivy_get_running_app
  carrito__suggest -.-> |SELECT| db_todoferre_db
  carrito__persist_draft -.-> |INSERT| db_todoferre_db
  carrito__load_draft -.-> |SELECT| db_todoferre_db
  carrito__finalize_order -.-> |SELECT| db_todoferre_db
  carrito__finalize_order -.-> |INSERT| db_todoferre_db
  carrito__finalize_order -.-> |SELECT| db_todoferre_db
  carrito__finalize_order -.-> |INSERT| db_todoferre_db
  carrito__finalize_order -.-> |DELETE| db_todoferre_db
classDef entry stroke-width:2px,stroke-dasharray:4 2;
```
