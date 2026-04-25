from database import Base, engine


def create():
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully")


def drop():
    confirm = input("Are you sure you want to DROP all tables? Type 'yes' to confirm: ")
    if confirm.lower() == "yes":
        Base.metadata.drop_all(bind=engine)
        print("All tables dropped")
    else:
        print("Cancelled")


def reset():
    confirm = input("Are you sure you want to RESET all tables? Type 'yes' to confirm: ")
    if confirm.lower() == "yes":
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("All tables reset successfully")
    else:
        print("Cancelled")


if __name__ == "__main__":
    print("What would you like to do?")
    print("1. Create tables")
    print("2. Drop tables")
    print("3. Reset tables")
    choice = input("Enter 1, 2, or 3: ").strip()

    if choice == "1":
        create()
    elif choice == "2":
        drop()
    elif choice == "3":
        reset()
    else:
        print("Invalid choice")
