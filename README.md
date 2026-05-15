# Website quản lý giải đấu cầu lông đôi nam

## Chức năng chính
- Tạo sẵn 8 đội, chia 2 bảng:
  - Bảng A: Đội 1, Đội 2, Đội 3, Đội 4
  - Bảng B: Đội 5, Đội 6, Đội 7, Đội 8
- Vòng bảng đánh vòng tròn 1 set 21 điểm.
- Thắng được 1 điểm, thua 0 điểm.
- Hiệu số = điểm thắng - điểm thua.
- Nếu 2 đội bằng điểm và hiệu số, hệ thống xét đối đầu để phân hạng.
- Tự tạo bán kết:
  - Nhất bảng A gặp Nhì bảng B.
  - Nhì bảng A gặp Nhất bảng B.
- Bán kết và chung kết đánh tối đa 3 set, mỗi set 15 điểm; đội thắng 2 set trước thắng trận.
- Có mục nhập tỉ số, bảng xếp hạng, roadmap giải đấu, thống kê VĐV và trang chi tiết VĐV.

## Cách chạy
```bash
cd giai_dau_cau_long
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate # macOS/Linux
pip install -r requirements.txt
python app.py
```

Sau đó mở trình duyệt tại:
```text
http://127.0.0.1:5000
```

## Cách thêm ảnh VĐV
Bạn có 2 cách:
1. Dán link ảnh trực tiếp vào ô `Link ảnh`.
2. Copy ảnh vào thư mục `static`, ví dụ `static/player1.jpg`, rồi nhập:
```text
/static/player1.jpg
```

## File quan trọng
- `app.py`: backend Flask, xử lý dữ liệu, trận đấu, bảng xếp hạng.
- `templates/`: giao diện HTML.
- `static/style.css`: giao diện CSS.
- `badminton.db`: tự sinh khi chạy lần đầu, dùng SQLite để lưu dữ liệu.
