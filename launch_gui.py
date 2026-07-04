import multiprocessing

multiprocessing.freeze_support()

from ae2_bus_scanner.app import main


if __name__ == "__main__":
    main()
