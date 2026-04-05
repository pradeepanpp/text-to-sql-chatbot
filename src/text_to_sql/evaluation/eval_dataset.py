# src/text_to_sql/evaluation/eval_dataset.py
"""
Evaluation Dataset — Phase 3.

100 question/SQL/answer triples covering:
  - All 6 tables
  - All 3 complexity tiers (simple / medium / complex)
  - English and Arabic questions
  - Edge cases (empty results, aggregations, joins)

Used by RAGAS evaluation and benchmark runner.
"""

# ─────────────────────────────────────────────
# DATASET STRUCTURE
# Each entry:
#   question     : natural language question
#   reference_sql: correct ground truth SQL
#   reference_ans: expected answer description
#   complexity   : simple / medium / complex
#   language     : en / ar
#   tables       : tables involved
# ─────────────────────────────────────────────

EVAL_DATASET = [

    # ══════════════════════════════════════════
    # SIMPLE — Single table, basic queries (40)
    # ══════════════════════════════════════════

    # customers table (8)
    {
        "question":     "How many customers are in the database?",
        "reference_sql": "SELECT COUNT(*) FROM customers",
        "reference_ans": "There are 175 customers in the database.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },
    {
        "question":     "List all customer names",
        "reference_sql": "SELECT customer_name FROM customers",
        "reference_ans": "Returns all 175 customer names.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },
    {
        "question":     "What is the customer name with index 1?",
        "reference_sql": "SELECT customer_name FROM customers WHERE customer_index = 1",
        "reference_ans": "The customer with index 1.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },
    {
        "question":     "Show me the first 10 customers",
        "reference_sql": "SELECT customer_name FROM customers LIMIT 10",
        "reference_ans": "Returns the first 10 customer names.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },
    {
        "question":     "كم عدد العملاء في قاعدة البيانات؟",
        "reference_sql": "SELECT COUNT(*) FROM customers",
        "reference_ans": "يوجد 175 عميلاً في قاعدة البيانات.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["customers"],
    },
    {
        "question":     "ما هو اسم العميل برقم 5؟",
        "reference_sql": "SELECT customer_name FROM customers WHERE customer_index = 5",
        "reference_ans": "اسم العميل برقم 5.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["customers"],
    },
    {
        "question":     "What is the maximum customer index?",
        "reference_sql": "SELECT MAX(customer_index) FROM customers",
        "reference_ans": "The maximum customer index value.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },
    {
        "question":     "What is the minimum customer index?",
        "reference_sql": "SELECT MIN(customer_index) FROM customers",
        "reference_ans": "The minimum customer index is 1.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["customers"],
    },

    # products table (6)
    {
        "question":     "How many products are there?",
        "reference_sql": "SELECT COUNT(*) FROM products",
        "reference_ans": "There are 30 products.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["products"],
    },
    {
        "question":     "List all product names",
        "reference_sql": "SELECT product_name FROM products",
        "reference_ans": "Returns all 30 product names.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["products"],
    },
    {
        "question":     "What is the product with index 1?",
        "reference_sql": "SELECT product_name FROM products WHERE product_index = 1",
        "reference_ans": "Product 1.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["products"],
    },
    {
        "question":     "ما هي أسماء جميع المنتجات؟",
        "reference_sql": "SELECT product_name FROM products",
        "reference_ans": "أسماء جميع المنتجات من المنتج 1 إلى المنتج 30.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["products"],
    },
    {
        "question":     "كم عدد المنتجات في قاعدة البيانات؟",
        "reference_sql": "SELECT COUNT(*) FROM products",
        "reference_ans": "يوجد 30 منتجاً في قاعدة البيانات.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["products"],
    },
    {
        "question":     "Show me the first 5 products",
        "reference_sql": "SELECT product_name FROM products LIMIT 5",
        "reference_ans": "Returns first 5 product names.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["products"],
    },

    # budgets table (6)
    {
        "question":     "What is the 2017 budget for Product 1?",
        "reference_sql": "SELECT budget_2017 FROM budgets WHERE product_name = 'Product 1'",
        "reference_ans": "The 2017 budget for Product 1.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "What is the total 2017 budget across all products?",
        "reference_sql": "SELECT SUM(budget_2017) FROM budgets",
        "reference_ans": "The total 2017 budget across all products.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "What is the average 2017 budget?",
        "reference_sql": "SELECT AVG(budget_2017) FROM budgets",
        "reference_ans": "The average 2017 budget across all products.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "Which product has the highest 2017 budget?",
        "reference_sql": "SELECT product_name, budget_2017 FROM budgets ORDER BY budget_2017 DESC LIMIT 1",
        "reference_ans": "The product with the highest 2017 budget.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "ما هو الميزانية الإجمالية لعام 2017؟",
        "reference_sql": "SELECT SUM(budget_2017) FROM budgets",
        "reference_ans": "الميزانية الإجمالية لجميع المنتجات عام 2017.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["budgets"],
    },
    {
        "question":     "How many products have a 2017 budget?",
        "reference_sql": "SELECT COUNT(*) FROM budgets",
        "reference_ans": "Number of products with a 2017 budget.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["budgets"],
    },

    # sales_orders table (10)
    {
        "question":     "How many sales orders are there?",
        "reference_sql": "SELECT COUNT(*) FROM sales_orders",
        "reference_ans": "There are 64,104 sales orders.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total line total across all orders?",
        "reference_sql": "SELECT SUM(line_total) FROM sales_orders",
        "reference_ans": "The total line total is $1,235,968,899.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the average order quantity?",
        "reference_sql": "SELECT AVG(order_quantity) FROM sales_orders",
        "reference_ans": "The average order quantity.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What channels are used for sales?",
        "reference_sql": "SELECT DISTINCT channel FROM sales_orders",
        "reference_ans": "The sales channels: Wholesale, Distributor, Export.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "How many Wholesale orders are there?",
        "reference_sql": "SELECT COUNT(*) FROM sales_orders WHERE channel = 'Wholesale'",
        "reference_ans": "Number of Wholesale channel orders.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total Wholesale sales amount?",
        "reference_sql": "SELECT SUM(line_total) FROM sales_orders WHERE channel = 'Wholesale'",
        "reference_ans": "Total Wholesale sales.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the maximum line total for any single order?",
        "reference_sql": "SELECT MAX(line_total) FROM sales_orders",
        "reference_ans": "The highest single order value.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "ما هو إجمالي المبيعات؟",
        "reference_sql": "SELECT SUM(line_total) FROM sales_orders",
        "reference_ans": "إجمالي المبيعات هو 1,235,968,899.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "كم عدد طلبات البيع؟",
        "reference_sql": "SELECT COUNT(*) FROM sales_orders",
        "reference_ans": "يوجد 64,104 طلب بيع.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What currencies are used in orders?",
        "reference_sql": "SELECT DISTINCT currency_code FROM sales_orders",
        "reference_ans": "The currencies used in orders.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["sales_orders"],
    },

    # regions / state_regions (10)
    {
        "question":     "How many regions are in the database?",
        "reference_sql": "SELECT COUNT(*) FROM regions",
        "reference_ans": "There are 994 regions.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "How many states are there?",
        "reference_sql": "SELECT COUNT(DISTINCT state) FROM regions",
        "reference_ans": "Number of distinct states.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "What regions exist in the South?",
        "reference_sql": "SELECT state FROM state_regions WHERE region = 'South'",
        "reference_ans": "States in the South region.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["state_regions"],
    },
    {
        "question":     "How many states are in the West region?",
        "reference_sql": "SELECT COUNT(*) FROM state_regions WHERE region = 'West'",
        "reference_ans": "Number of states in the West region.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["state_regions"],
    },
    {
        "question":     "What is the region for California?",
        "reference_sql": "SELECT region FROM state_regions WHERE state = 'California'",
        "reference_ans": "California is in the West region.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["state_regions"],
    },
    {
        "question":     "List all distinct regions",
        "reference_sql": "SELECT DISTINCT region FROM state_regions",
        "reference_ans": "The distinct regions: South, West, Midwest, Northeast.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["state_regions"],
    },
    {
        "question":     "What is the average population of regions?",
        "reference_sql": "SELECT AVG(population) FROM regions",
        "reference_ans": "The average population across all regions.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "How many cities are in California?",
        "reference_sql": "SELECT COUNT(*) FROM regions WHERE state = 'California'",
        "reference_ans": "Number of cities in California.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "كم عدد المناطق في قاعدة البيانات؟",
        "reference_sql": "SELECT COUNT(*) FROM regions",
        "reference_ans": "يوجد 994 منطقة في قاعدة البيانات.",
        "complexity":   "simple",
        "language":     "ar",
        "tables":       ["regions"],
    },
    {
        "question":     "What are the distinct time zones in the regions?",
        "reference_sql": "SELECT DISTINCT time_zone FROM regions",
        "reference_ans": "The distinct time zones in regions.",
        "complexity":   "simple",
        "language":     "en",
        "tables":       ["regions"],
    },

    # ══════════════════════════════════════════
    # MEDIUM — Joins, GROUP BY, Rankings (35)
    # ══════════════════════════════════════════

    {
        "question":     "What are the top 5 customers by total line total?",
        "reference_sql": "SELECT c.customer_name, SUM(s.line_total) as total FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY total DESC LIMIT 5",
        "reference_ans": "Top 5 customers by revenue.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What is the total sales broken down by channel?",
        "reference_sql": "SELECT channel, SUM(line_total) as total FROM sales_orders GROUP BY channel ORDER BY total DESC",
        "reference_ans": "Total sales per channel.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which product has the highest total order quantity?",
        "reference_sql": "SELECT p.product_name, SUM(s.order_quantity) as total FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY total DESC LIMIT 1",
        "reference_ans": "The product with highest total quantity ordered.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "What is the average order value per channel?",
        "reference_sql": "SELECT channel, AVG(line_total) as avg_value FROM sales_orders GROUP BY channel",
        "reference_ans": "Average order value per channel.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Top 10 products by total revenue",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as revenue FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY revenue DESC LIMIT 10",
        "reference_ans": "Top 10 products by revenue.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "How many orders does each customer have?",
        "reference_sql": "SELECT c.customer_name, COUNT(*) as order_count FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY order_count DESC",
        "reference_ans": "Order count per customer.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What is the total sales for each year?",
        "reference_sql": "SELECT strftime('%Y', order_date) as year, SUM(line_total) as total FROM sales_orders GROUP BY year ORDER BY year",
        "reference_ans": "Total sales broken down by year.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "ما هي أكبر 5 عملاء من حيث إجمالي المبيعات؟",
        "reference_sql": "SELECT c.customer_name, SUM(s.line_total) as total FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY total DESC LIMIT 5",
        "reference_ans": "أكبر 5 عملاء من حيث إجمالي المبيعات.",
        "complexity":   "medium",
        "language":     "ar",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What is the minimum order value per channel?",
        "reference_sql": "SELECT channel, MIN(line_total) as min_value FROM sales_orders GROUP BY channel",
        "reference_ans": "Minimum order value per channel.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which warehouse has the most orders?",
        "reference_sql": "SELECT warehouse_code, COUNT(*) as total FROM sales_orders GROUP BY warehouse_code ORDER BY total DESC LIMIT 1",
        "reference_ans": "The warehouse with the most orders.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total sales per product?",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as total FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY total DESC",
        "reference_ans": "Total sales per product.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "How many orders were placed in 2021?",
        "reference_sql": "SELECT COUNT(*) FROM sales_orders WHERE order_date LIKE '2021%'",
        "reference_ans": "Number of orders placed in 2021.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the bottom 5 products by revenue?",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as revenue FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY revenue ASC LIMIT 5",
        "reference_ans": "Bottom 5 products by revenue.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "What is the average unit price per product?",
        "reference_sql": "SELECT p.product_name, AVG(s.unit_price) as avg_price FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY avg_price DESC",
        "reference_ans": "Average unit price per product.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "Which customer placed the most orders?",
        "reference_sql": "SELECT c.customer_name, COUNT(*) as orders FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY orders DESC LIMIT 1",
        "reference_ans": "The customer who placed the most orders.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What is the total revenue by currency?",
        "reference_sql": "SELECT currency_code, SUM(line_total) as total FROM sales_orders GROUP BY currency_code ORDER BY total DESC",
        "reference_ans": "Total revenue broken down by currency.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "ما هي إجمالي المبيعات لكل قناة توزيع؟",
        "reference_sql": "SELECT channel, SUM(line_total) as total FROM sales_orders GROUP BY channel ORDER BY total DESC",
        "reference_ans": "إجمالي المبيعات لكل قناة توزيع.",
        "complexity":   "medium",
        "language":     "ar",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total cost versus total revenue?",
        "reference_sql": "SELECT SUM(total_unit_cost) as total_cost, SUM(line_total) as total_revenue FROM sales_orders",
        "reference_ans": "Total cost compared to total revenue.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which month had the highest total sales?",
        "reference_sql": "SELECT strftime('%Y-%m', order_date) as month, SUM(line_total) as total FROM sales_orders GROUP BY month ORDER BY total DESC LIMIT 1",
        "reference_ans": "The month with the highest total sales.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "How many unique warehouses are used?",
        "reference_sql": "SELECT COUNT(DISTINCT warehouse_code) FROM sales_orders",
        "reference_ans": "Number of unique warehouses.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total profit (line_total minus total_unit_cost) per channel?",
        "reference_sql": "SELECT channel, SUM(line_total - total_unit_cost) as profit FROM sales_orders GROUP BY channel ORDER BY profit DESC",
        "reference_ans": "Total profit per channel.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Top 3 warehouses by total revenue",
        "reference_sql": "SELECT warehouse_code, SUM(line_total) as revenue FROM sales_orders GROUP BY warehouse_code ORDER BY revenue DESC LIMIT 3",
        "reference_ans": "Top 3 warehouses by revenue.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "ما هو المنتج الأكثر مبيعاً من حيث الكمية؟",
        "reference_sql": "SELECT p.product_name, SUM(s.order_quantity) as total FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY total DESC LIMIT 1",
        "reference_ans": "المنتج الأكثر مبيعاً من حيث الكمية.",
        "complexity":   "medium",
        "language":     "ar",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "What are the 2017 budgets sorted from highest to lowest?",
        "reference_sql": "SELECT product_name, budget_2017 FROM budgets ORDER BY budget_2017 DESC",
        "reference_ans": "Products sorted by 2017 budget descending.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "What is the average number of orders per customer?",
        "reference_sql": "SELECT AVG(order_count) FROM (SELECT customer_name_index, COUNT(*) as order_count FROM sales_orders GROUP BY customer_name_index)",
        "reference_ans": "Average orders per customer.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which state has the most cities in the database?",
        "reference_sql": "SELECT state, COUNT(*) as city_count FROM regions GROUP BY state ORDER BY city_count DESC LIMIT 1",
        "reference_ans": "The state with the most cities.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "What is the total sales for Product 1?",
        "reference_sql": "SELECT SUM(s.line_total) FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index WHERE p.product_name = 'Product 1'",
        "reference_ans": "Total sales for Product 1.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "How many orders use USD currency?",
        "reference_sql": "SELECT COUNT(*) FROM sales_orders WHERE currency_code = 'USD'",
        "reference_ans": "Number of orders in USD.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the average median income across all regions?",
        "reference_sql": "SELECT AVG(median_income) FROM regions",
        "reference_ans": "Average median income across all regions.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["regions"],
    },
    {
        "question":     "Which product has the lowest 2017 budget?",
        "reference_sql": "SELECT product_name, budget_2017 FROM budgets ORDER BY budget_2017 ASC LIMIT 1",
        "reference_ans": "Product with the lowest 2017 budget.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["budgets"],
    },
    {
        "question":     "ما هو إجمالي عدد الطلبات لكل قناة؟",
        "reference_sql": "SELECT channel, COUNT(*) as total FROM sales_orders GROUP BY channel",
        "reference_ans": "إجمالي عدد الطلبات لكل قناة توزيع.",
        "complexity":   "medium",
        "language":     "ar",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total quantity ordered per product?",
        "reference_sql": "SELECT p.product_name, SUM(s.order_quantity) as qty FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY qty DESC",
        "reference_ans": "Total quantity ordered per product.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "What is the highest revenue generating customer?",
        "reference_sql": "SELECT c.customer_name, SUM(s.line_total) as revenue FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY revenue DESC LIMIT 1",
        "reference_ans": "The highest revenue generating customer.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "How many orders were placed per year?",
        "reference_sql": "SELECT strftime('%Y', order_date) as year, COUNT(*) as orders FROM sales_orders GROUP BY year ORDER BY year",
        "reference_ans": "Number of orders per year.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "What is the total revenue from the South region states?",
        "reference_sql": "SELECT SUM(s.line_total) FROM sales_orders s JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code WHERE sr.region = 'South'",
        "reference_ans": "Total revenue from South region deliveries.",
        "complexity":   "medium",
        "language":     "en",
        "tables":       ["sales_orders", "regions", "state_regions"],
    },

    # ══════════════════════════════════════════
    # COMPLEX — Multi-table, subqueries (25)
    # ══════════════════════════════════════════

    {
        "question":     "Compare total sales versus 2017 budget for each product",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as actual_sales, b.budget_2017 FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 ORDER BY actual_sales DESC",
        "reference_ans": "Comparison of actual sales vs 2017 budget per product.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "What percentage of total revenue came from each channel?",
        "reference_sql": "SELECT channel, SUM(line_total) as revenue, ROUND(SUM(line_total) * 100.0 / (SELECT SUM(line_total) FROM sales_orders), 2) as pct FROM sales_orders GROUP BY channel",
        "reference_ans": "Percentage of total revenue per channel.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which products had actual sales above their 2017 budget?",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as sales, b.budget_2017 FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 HAVING sales > b.budget_2017",
        "reference_ans": "Products where actual sales exceeded 2017 budget.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "What is the revenue breakdown by region for the top 3 customers?",
        "reference_sql": "SELECT c.customer_name, sr.region, SUM(s.line_total) as revenue FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code WHERE c.customer_name IN (SELECT c2.customer_name FROM sales_orders s2 JOIN customers c2 ON s2.customer_name_index = c2.customer_index GROUP BY c2.customer_name ORDER BY SUM(s2.line_total) DESC LIMIT 3) GROUP BY c.customer_name, sr.region",
        "reference_ans": "Revenue by region for the top 3 customers.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "customers", "regions", "state_regions"],
    },
    {
        "question":     "Compare revenue versus budget across all products and rank them",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as revenue, b.budget_2017, ROUND((SUM(s.line_total) - b.budget_2017) / b.budget_2017 * 100, 2) as pct_diff FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 ORDER BY pct_diff DESC",
        "reference_ans": "Products ranked by percentage difference between sales and budget.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "Which region had the highest average order value?",
        "reference_sql": "SELECT sr.region, AVG(s.line_total) as avg_order FROM sales_orders s JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code GROUP BY sr.region ORDER BY avg_order DESC LIMIT 1",
        "reference_ans": "Region with the highest average order value.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "regions", "state_regions"],
    },
    {
        "question":     "What is the total profit margin per product?",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as revenue, SUM(s.total_unit_cost) as cost, ROUND((SUM(s.line_total) - SUM(s.total_unit_cost)) / SUM(s.line_total) * 100, 2) as margin_pct FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY margin_pct DESC",
        "reference_ans": "Profit margin percentage per product.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "قارن المبيعات الفعلية مقابل ميزانية 2017 لكل منتج",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as actual, b.budget_2017 FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017",
        "reference_ans": "مقارنة المبيعات الفعلية مع ميزانية 2017 لكل منتج.",
        "complexity":   "complex",
        "language":     "ar",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "Which customers have above average order values?",
        "reference_sql": "SELECT c.customer_name, AVG(s.line_total) as avg_order FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name HAVING avg_order > (SELECT AVG(line_total) FROM sales_orders) ORDER BY avg_order DESC",
        "reference_ans": "Customers with above average order values.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What percentage of each product's sales came from the Wholesale channel?",
        "reference_sql": "SELECT p.product_name, ROUND(SUM(CASE WHEN s.channel = 'Wholesale' THEN s.line_total ELSE 0 END) * 100.0 / SUM(s.line_total), 2) as wholesale_pct FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY wholesale_pct DESC",
        "reference_ans": "Percentage of Wholesale sales per product.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
    {
        "question":     "Which region generated the most revenue and what were the top 3 products there?",
        "reference_sql": "SELECT sr.region, p.product_name, SUM(s.line_total) as revenue FROM sales_orders s JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code JOIN products p ON s.product_description_index = p.product_index GROUP BY sr.region, p.product_name ORDER BY revenue DESC LIMIT 10",
        "reference_ans": "Top products in the highest revenue region.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "regions", "state_regions", "products"],
    },
    {
        "question":     "What is the year-over-year revenue growth?",
        "reference_sql": "SELECT strftime('%Y', order_date) as year, SUM(line_total) as revenue FROM sales_orders GROUP BY year ORDER BY year",
        "reference_ans": "Revenue trend by year.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which customers have never ordered Product 1?",
        "reference_sql": "SELECT c.customer_name FROM customers c WHERE c.customer_index NOT IN (SELECT DISTINCT s.customer_name_index FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index WHERE p.product_name = 'Product 1')",
        "reference_ans": "Customers who have never ordered Product 1.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["customers", "sales_orders", "products"],
    },
    {
        "question":     "What is the revenue contribution of each region as a percentage?",
        "reference_sql": "SELECT sr.region, SUM(s.line_total) as revenue, ROUND(SUM(s.line_total) * 100.0 / (SELECT SUM(line_total) FROM sales_orders), 2) as pct FROM sales_orders s JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code GROUP BY sr.region ORDER BY revenue DESC",
        "reference_ans": "Revenue percentage by region.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "regions", "state_regions"],
    },
    {
        "question":     "ما هي نسبة الإيرادات من كل قناة توزيع؟",
        "reference_sql": "SELECT channel, ROUND(SUM(line_total) * 100.0 / (SELECT SUM(line_total) FROM sales_orders), 2) as pct FROM sales_orders GROUP BY channel",
        "reference_ans": "نسبة الإيرادات من كل قناة توزيع.",
        "complexity":   "complex",
        "language":     "ar",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Which products are underperforming versus their 2017 budget by more than 10%?",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as sales, b.budget_2017, ROUND((b.budget_2017 - SUM(s.line_total)) / b.budget_2017 * 100, 2) as gap_pct FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 HAVING gap_pct > 10 ORDER BY gap_pct DESC",
        "reference_ans": "Products underperforming vs budget by more than 10%.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "What is the average profit margin across all channels?",
        "reference_sql": "SELECT channel, ROUND(AVG((line_total - total_unit_cost) / line_total * 100), 2) as avg_margin FROM sales_orders GROUP BY channel",
        "reference_ans": "Average profit margin per channel.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Rank customers by both revenue and order count",
        "reference_sql": "SELECT c.customer_name, SUM(s.line_total) as revenue, COUNT(*) as orders FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY revenue DESC LIMIT 20",
        "reference_ans": "Customers ranked by revenue and order count.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "What is the total revenue per region per year?",
        "reference_sql": "SELECT sr.region, strftime('%Y', s.order_date) as year, SUM(s.line_total) as revenue FROM sales_orders s JOIN regions r ON s.delivery_region_index = r.id JOIN state_regions sr ON r.state_code = sr.state_code GROUP BY sr.region, year ORDER BY year, revenue DESC",
        "reference_ans": "Revenue broken down by region and year.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "regions", "state_regions"],
    },
    {
        "question":     "Which customer has the highest average order value?",
        "reference_sql": "SELECT c.customer_name, AVG(s.line_total) as avg_value FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index GROUP BY c.customer_name ORDER BY avg_value DESC LIMIT 1",
        "reference_ans": "Customer with the highest average order value.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "customers"],
    },
    {
        "question":     "ما هي المنتجات التي تجاوزت مبيعاتها ميزانية 2017؟",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as sales, b.budget_2017 FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 HAVING sales > b.budget_2017",
        "reference_ans": "المنتجات التي تجاوزت مبيعاتها ميزانية 2017.",
        "complexity":   "complex",
        "language":     "ar",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "What is the revenue split between products for the top 3 customers?",
        "reference_sql": "SELECT c.customer_name, p.product_name, SUM(s.line_total) as revenue FROM sales_orders s JOIN customers c ON s.customer_name_index = c.customer_index JOIN products p ON s.product_description_index = p.product_index WHERE c.customer_name IN (SELECT c2.customer_name FROM sales_orders s2 JOIN customers c2 ON s2.customer_name_index = c2.customer_index GROUP BY c2.customer_name ORDER BY SUM(s2.line_total) DESC LIMIT 3) GROUP BY c.customer_name, p.product_name ORDER BY c.customer_name, revenue DESC",
        "reference_ans": "Product revenue breakdown for top 3 customers.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "customers", "products"],
    },
    {
        "question":     "Which warehouse had the highest profit margin?",
        "reference_sql": "SELECT warehouse_code, ROUND(AVG((line_total - total_unit_cost) / line_total * 100), 2) as margin FROM sales_orders GROUP BY warehouse_code ORDER BY margin DESC LIMIT 1",
        "reference_ans": "Warehouse with the highest average profit margin.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders"],
    },
    {
        "question":     "Show the budget achievement rate per product sorted by highest achiever",
        "reference_sql": "SELECT p.product_name, SUM(s.line_total) as sales, b.budget_2017, ROUND(SUM(s.line_total) / b.budget_2017 * 100, 2) as achievement_pct FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index JOIN budgets b ON p.product_name = b.product_name GROUP BY p.product_name, b.budget_2017 ORDER BY achievement_pct DESC",
        "reference_ans": "Budget achievement rate per product.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products", "budgets"],
    },
    {
        "question":     "What is the correlation between order quantity and line total by product?",
        "reference_sql": "SELECT p.product_name, AVG(s.order_quantity) as avg_qty, AVG(s.line_total) as avg_value FROM sales_orders s JOIN products p ON s.product_description_index = p.product_index GROUP BY p.product_name ORDER BY avg_value DESC",
        "reference_ans": "Average quantity and value per product.",
        "complexity":   "complex",
        "language":     "en",
        "tables":       ["sales_orders", "products"],
    },
]


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def get_by_complexity(complexity: str) -> list:
    """Filter dataset by complexity tier."""
    return [q for q in EVAL_DATASET if q["complexity"] == complexity]


def get_by_language(language: str) -> list:
    """Filter dataset by language."""
    return [q for q in EVAL_DATASET if q["language"] == language]


def get_summary() -> dict:
    """Return dataset statistics."""
    total    = len(EVAL_DATASET)
    simple   = len(get_by_complexity("simple"))
    medium   = len(get_by_complexity("medium"))
    complex_ = len(get_by_complexity("complex"))
    english  = len(get_by_language("en"))
    arabic   = len(get_by_language("ar"))

    return {
        "total":   total,
        "simple":  simple,
        "medium":  medium,
        "complex": complex_,
        "english": english,
        "arabic":  arabic,
    }