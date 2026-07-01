"""Populate the database with demo users, drivers, rides and alerts.

Usage:  python manage.py seed_data
Login passwords are all "password123".
"""
import random

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import DriverProfile, TrustedContact, User
from rides.models import EmergencyAlert, Rating, Ride, RideTracking
from rides.utils import build_straight_route, estimate_eta_minutes, haversine_m

PASSWORD = "password123"

# A few real-ish coordinates around Lagos, Nigeria.
PLACES = [
    ("Ikeja City Mall", 6.6018, 3.3515),
    ("Lekki Phase 1", 6.4474, 3.4720),
    ("Victoria Island", 6.4281, 3.4219),
    ("Yaba Tech", 6.5176, 3.3756),
    ("Surulere", 6.5006, 3.3556),
    ("Ajah", 6.4698, 3.5852),
]


class Command(BaseCommand):
    help = "Seed the database with demo data."

    def handle(self, *args, **options):
        self.stdout.write("Seeding SafeDrive demo data…")

        # Admin
        admin, created = User.objects.get_or_create(
            email="admin@safedrive.test",
            defaults={
                "username": "admin@safedrive.test",
                "name": "Site Admin",
                "phone": "+2348000000000",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password(PASSWORD)
        admin.is_staff = True
        admin.is_superuser = True
        admin.role = User.Role.ADMIN
        admin.save()

        # Riders
        riders = []
        for i in range(1, 4):
            r, _ = User.objects.get_or_create(
                email=f"rider{i}@safedrive.test",
                defaults={
                    "username": f"rider{i}@safedrive.test",
                    "name": f"Rider {i}",
                    "phone": f"+23480100000{i}",
                    "role": User.Role.RIDER,
                },
            )
            r.set_password(PASSWORD)
            r.save()
            riders.append(r)
            TrustedContact.objects.get_or_create(
                rider=r, name=f"Contact of Rider {i}",
                defaults={"phone": f"+23480555000{i}", "email": f"contact{i}@family.test"},
            )

        # Drivers (mix of approved + pending)
        drivers = []
        for i in range(1, 4):
            d, _ = User.objects.get_or_create(
                email=f"driver{i}@safedrive.test",
                defaults={
                    "username": f"driver{i}@safedrive.test",
                    "name": f"Driver {i}",
                    "phone": f"+23480200000{i}",
                    "role": User.Role.DRIVER,
                    "status": User.Status.ACTIVE,
                },
            )
            d.set_password(PASSWORD)
            d.save()
            status = (
                DriverProfile.Verification.APPROVED if i < 3
                else DriverProfile.Verification.PENDING
            )
            place = random.choice(PLACES)
            dp, _ = DriverProfile.objects.get_or_create(user=d)
            dp.license_number = f"LIC-{1000 + i}"
            dp.vehicle_type = random.choice(["Toyota Corolla", "Honda Accord", "Kia Rio"])
            dp.vehicle_number = f"LAG-{random.randint(100, 999)}XY"
            dp.verification_status = status
            dp.is_online = i < 3
            dp.current_lat, dp.current_lng = place[1], place[2]
            dp.save()
            drivers.append(d)

        approved_drivers = [d for d in drivers if d.driver_profile.is_approved]

        # Completed rides with ratings + tracking
        for i in range(5):
            rider = random.choice(riders)
            driver = random.choice(approved_drivers)
            p = random.choice(PLACES)
            dest = random.choice([x for x in PLACES if x != p])
            route = build_straight_route((p[1], p[2]), (dest[1], dest[2]))
            distance = haversine_m(p[1], p[2], dest[1], dest[2])
            ride = Ride.objects.create(
                rider=rider,
                driver=driver,
                pickup_location=p[0],
                pickup_lat=p[1],
                pickup_lng=p[2],
                destination=dest[0],
                destination_lat=dest[1],
                destination_lng=dest[2],
                planned_route=route,
                eta_minutes=estimate_eta_minutes(distance),
                status=Ride.Status.COMPLETED,
                start_time=timezone.now(),
                end_time=timezone.now(),
            )
            for pt in route[::2]:
                RideTracking.objects.create(ride=ride, latitude=pt[0], longitude=pt[1])
            Rating.objects.create(
                ride=ride, rider=rider, driver=driver,
                score=random.randint(3, 5), review="Smooth and safe trip.",
            )

        # One active ride + an SOS alert for the admin dashboard demo
        rider = riders[0]
        driver = approved_drivers[0]
        p, dest = PLACES[0], PLACES[1]
        active = Ride.objects.create(
            rider=rider, driver=driver,
            pickup_location=p[0], pickup_lat=p[1], pickup_lng=p[2],
            destination=dest[0], destination_lat=dest[1], destination_lng=dest[2],
            planned_route=build_straight_route((p[1], p[2]), (dest[1], dest[2])),
            eta_minutes=estimate_eta_minutes(haversine_m(p[1], p[2], dest[1], dest[2])),
            status=Ride.Status.ONGOING, start_time=timezone.now(),
        )
        RideTracking.objects.create(ride=active, latitude=p[1], longitude=p[2])
        EmergencyAlert.objects.create(
            ride=active, rider=rider, raised_by=rider,
            kind=EmergencyAlert.Kind.SOS, latitude=p[1], longitude=p[2],
            location=p[0], message="Demo SOS alert.",
        )

        self.stdout.write(self.style.SUCCESS("Done!"))
        self.stdout.write("Logins (password: password123):")
        self.stdout.write("  admin@safedrive.test  (admin)")
        self.stdout.write("  rider1@safedrive.test (rider)")
        self.stdout.write("  driver1@safedrive.test (approved driver)")
        self.stdout.write("  driver3@safedrive.test (pending driver)")
