from core.drawings.graphical_takeoff import ScaleCalibration

def test_pixel_calibration_is_meter_accurate():
    scale=ScaleCalibration(0.01,"m","m","0.01 m/px","pixel-calibration")
    assert scale.length(1000)==10
    assert scale.area(1000000)==100
