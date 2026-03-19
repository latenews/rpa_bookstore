"""
플랫폼별 Selenium CSS/XPath 셀렉터 모음
UI 변경 시 이 파일만 수정하면 됩니다.
"""

ALADIN = {
    # 로그인
    "login_id":         "input#id",
    "login_pw":         "input#pwd",
    "login_btn":        "button.btn_login",
    "login_check":      "a.myAladin",          # 로그인 성공 확인용

    # 중고 판매 관리
    "used_menu":        "a[href*='mystore']",
    "used_list_url":    "https://www.aladin.co.kr/mystore/UsedShopMyGoods.aspx",

    # 상품 검색
    "search_input":     "input#searchKeyword",
    "search_btn":       "button#searchBtn",
    "search_result":    "table.tb_list tbody tr",
    "item_checkbox":    "input[type='checkbox']",

    # 품절/삭제 처리
    "soldout_btn":      "button[onclick*='soldOut']",
    "delete_btn":       "button[onclick*='delete']",
    "confirm_ok":       "button.btn_ok",
}

GADDONG = {
    # 로그인
    "login_url":        "https://www.gadadong.com/member/login",
    "login_id":         "input[name='userId']",
    "login_pw":         "input[name='userPwd']",
    "login_btn":        "button[type='submit']",
    "login_check":      "a.my-page",

    # 상품 관리
    "goods_url":        "https://www.gadadong.com/mypage/goods/list",
    "search_input":     "input[name='keyword']",
    "search_btn":       "button.btn-search",
    "search_result":    "ul.goods-list li",

    # 품절/삭제
    "soldout_btn":      "button.btn-soldout",
    "delete_btn":       "button.btn-delete",
    "confirm_ok":       "button.btn-confirm",
}

BOOKCOA = {
    # 로그인
    "login_url":        "https://www.bookcoa.com/login",
    "login_id":         "input#loginId",
    "login_pw":         "input#loginPw",
    "login_btn":        "button.login-btn",
    "login_check":      "span.user-name",

    # 상품 관리
    "goods_url":        "https://www.bookcoa.com/mypage/goods",
    "search_input":     "input.search-input",
    "search_btn":       "button.search-btn",
    "search_result":    "div.goods-item",

    # 품절/삭제
    "soldout_btn":      "button.soldout",
    "delete_btn":       "button.delete",
    "confirm_ok":       "button.ok",
}
