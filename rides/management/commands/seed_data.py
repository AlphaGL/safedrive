"""Populate the database with a rich set of demo data.

Usage:  python manage.py seed_data
All login passwords are "password123". Re-running wipes previous rides,
ratings, alerts and reports (users are kept / updated).
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import DriverProfile, TrustedContact, User
from rides.models import EmergencyAlert, IncidentReport, Rating, Ride, RideTracking
from rides.utils import build_straight_route, estimate_eta_minutes, haversine_m

PASSWORD = "password123"

# Landmarks around Lagos, Nigeria (name, lat, lng)
PLACES = [
    ("Ikeja City Mall", 6.6018, 3.3515),
    ("Lekki Phase 1", 6.4474, 3.4720),
    ("Victoria Island", 6.4281, 3.4219),
    ("Yaba Tech", 6.5176, 3.3756),
    ("Surulere", 6.5006, 3.3556),
    ("Ajah", 6.4698, 3.5852),
    ("Ikoyi", 6.4529, 3.4360),
    ("Oshodi", 6.5556, 3.3489),
    ("Maryland Mall", 6.5719, 3.3679),
    ("Festac Town", 6.4650, 3.2870),
    ("Gbagada", 6.5450, 3.3860),
    ("Apapa", 6.4500, 3.3600),
]

# (name, gender, portrait_index) — randomuser.me has men/women/0-99.jpg
RIDER_DATA = [
    ("Amara Okafor", "women", 25),
    ("Chidi Nwosu", "men", 32),
    ("Zainab Bello", "women", 44),
    ("Emeka Eze", "men", 12),
    ("Ngozi Adeyemi", "women", 8),
    ("Tunde Balogun", "men", 47),
    ("Fatima Sani", "women", 19),
    ("Obinna Okonkwo", "men", 5),
    ("Blessing Ade", "women", 60),
    ("Yusuf Ibrahim", "men", 23),
]

# (name, gender, portrait_index, vehicle_type, verification)
DRIVER_DATA = [
    ("Femi Adebayo", "men", 41, "Toyota Corolla", "approved"),
    ("Grace Uche", "women", 33, "Honda Accord", "approved"),
    ("Musa Danjuma", "men", 51, "Kia Rio", "approved"),
    ("Kelechi Obi", "men", 15, "Toyota Camry", "approved"),
    ("Halima Yusuf", "women", 52, "Hyundai Elantra", "approved"),
    ("Segun Ojo", "men", 60, "Toyota Corolla", "approved"),
    ("Ifeoma Nnaji", "women", 27, "Honda Civic", "approved"),
    ("Bode Martins", "men", 9, "Lexus ES", "pending"),
    ("Aisha Lawal", "women", 14, "Kia Cerato", "pending"),
    ("Uche Okoro", "men", 3, "Toyota Corolla", "suspended"),
]

CAR_IMAGES = [
    "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?auto=format&fit=crop&w=600&q=80",
]

REVIEWS = [
    "Smooth and safe trip, thank you!",
    "Very professional driver, arrived on time.",
    "Clean car and careful driving.",
    "Great conversation and a comfortable ride.",
    "Felt safe the whole way. Highly recommend.",
    "Good driver, took the fastest route.",
    "Polite and punctual. Would ride again.",
    "",
]

ALERT_MESSAGES = {
    "sos": "SOS triggered by rider during active trip.",
    "route_deviation": "Vehicle drifted significantly off the planned route.",
    "stationary": "Vehicle has remained stationary for an unusual amount of time.",
    "eta_exceeded": "Trip is taking far longer than the estimated time.",
    "incident": "Rider reported feeling unsafe during the trip.",
}


def portrait(gender, idx):
    return f"https://randomuser.me/api/portraits/{gender}/{idx}.jpg"


def plate():
    return f"LAG-{random.randint(100, 999)}{random.choice('ABCDEFGHJKL')}{random.choice('MNPQRSTUVWXY')}"


class Command(BaseCommand):
    help = "Seed the database with a rich set of demo data."

    def handle(self, *args, **options):
        self.stdout.write("Seeding SafeDrive demo data…")

        # Clear transactional data for a clean, deterministic seed.
        RideTracking.objects.all().delete()
        EmergencyAlert.objects.all().delete()
        IncidentReport.objects.all().delete()
        Rating.objects.all().delete()
        Ride.objects.all().delete()

        # ---- Admin ----
        admin = self._user(
            "admin@safedrive.test", "Site Admin", "+2348000000000",
            User.Role.ADMIN, avatar=portrait("men", 68),
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.status = User.Status.ACTIVE
        admin.save()

        # ---- Riders ----
        riders = []
        for i, (name, gender, idx) in enumerate(RIDER_DATA, start=1):
            r = self._user(
                f"rider{i}@safedrive.test", name, f"+23480100000{i:02d}",
                User.Role.RIDER, avatar=portrait(gender, idx),
            )
            riders.append(r)
            # 1–2 trusted contacts each
            TrustedContact.objects.get_or_create(
                rider=r, name=f"{name.split()[0]}'s Next of Kin",
                defaults={"phone": f"+23480555000{i:02d}", "email": f"family{i}@contacts.test"},
            )
            if i % 2 == 0:
                TrustedContact.objects.get_or_create(
                    rider=r, name=f"{name.split()[0]}'s Friend",
                    defaults={"phone": f"+23480777000{i:02d}", "email": f"friend{i}@contacts.test"},
                )

        # ---- Drivers ----
        drivers = []
        for i, (name, gender, idx, vtype, verif) in enumerate(DRIVER_DATA, start=1):
            status = User.Status.ACTIVE
            if verif == "pending":
                status = User.Status.PENDING
            elif verif == "suspended":
                status = User.Status.SUSPENDED
            d = self._user(
                f"driver{i}@safedrive.test", name, f"+23480200000{i:02d}",
                User.Role.DRIVER, avatar=portrait(gender, idx), status=status,
            )
            place = random.choice(PLACES)
            dp, _ = DriverProfile.objects.get_or_create(user=d)
            dp.license_number = f"LIC-{2000 + i}"
            dp.vehicle_type = vtype
            dp.vehicle_number = plate()
            dp.verification_status = getattr(DriverProfile.Verification, verif.upper())
            dp.is_online = verif == "approved" and i % 3 != 0
            dp.current_lat, dp.current_lng = place[1], place[2]
            dp.vehicle_image_url = CAR_IMAGES[(i - 1) % len(CAR_IMAGES)]
            dp.save()
            drivers.append(d)

        approved = [d for d in drivers if d.driver_profile.is_approved]

        # ---- Completed rides + tracking + ratings ----
        now = timezone.now()
        for _ in range(30):
            rider = random.choice(riders)
            driver = random.choice(approved)
            p, dest = random.sample(PLACES, 2)
            route = build_straight_route((p[1], p[2]), (dest[1], dest[2]))
            distance = haversine_m(p[1], p[2], dest[1], dest[2])
            started = now - timedelta(days=random.randint(0, 20), hours=random.randint(0, 12))
            ride = Ride.objects.create(
                rider=rider, driver=driver,
                pickup_location=p[0], pickup_lat=p[1], pickup_lng=p[2],
                destination=dest[0], destination_lat=dest[1], destination_lng=dest[2],
                planned_route=route, eta_minutes=estimate_eta_minutes(distance),
                status=Ride.Status.COMPLETED,
                start_time=started, end_time=started + timedelta(minutes=random.randint(12, 40)),
                created_at=started,
            )
            for pt in route[::2]:
                RideTracking.objects.create(ride=ride, latitude=pt[0], longitude=pt[1])
            Rating.objects.create(
                ride=ride, rider=rider, driver=driver,
                score=random.choices([3, 4, 5], weights=[1, 3, 6])[0],
                review=random.choice(REVIEWS),
            )

        # ---- Active (ongoing) rides ----
        active_rides = []
        for driver in approved[:3]:
            rider = random.choice(riders)
            p, dest = random.sample(PLACES, 2)
            ride = Ride.objects.create(
                rider=rider, driver=driver,
                pickup_location=p[0], pickup_lat=p[1], pickup_lng=p[2],
                destination=dest[0], destination_lat=dest[1], destination_lng=dest[2],
                planned_route=build_straight_route((p[1], p[2]), (dest[1], dest[2])),
                eta_minutes=estimate_eta_minutes(haversine_m(p[1], p[2], dest[1], dest[2])),
                status=Ride.Status.ONGOING, start_time=now - timedelta(minutes=random.randint(5, 20)),
            )
            RideTracking.objects.create(ride=ride, latitude=p[1], longitude=p[2])
            active_rides.append(ride)

        # ---- Pending requests directed at approved drivers ----
        for driver in approved[3:6]:
            rider = random.choice(riders)
            p, dest = random.sample(PLACES, 2)
            Ride.objects.create(
                rider=rider, driver=driver,
                pickup_location=p[0], pickup_lat=p[1], pickup_lng=p[2],
                destination=dest[0], destination_lat=dest[1], destination_lng=dest[2],
                planned_route=build_straight_route((p[1], p[2]), (dest[1], dest[2])),
                eta_minutes=estimate_eta_minutes(haversine_m(p[1], p[2], dest[1], dest[2])),
                status=Ride.Status.REQUESTED,
            )

        # ---- Emergency alerts (mixed kinds + statuses) ----
        kinds = ["sos", "route_deviation", "stationary", "eta_exceeded", "sos"]
        statuses = [
            EmergencyAlert.Status.ACTIVE, EmergencyAlert.Status.ACTIVE,
            EmergencyAlert.Status.ACKNOWLEDGED, EmergencyAlert.Status.RESOLVED,
        ]
        for i, kind in enumerate(kinds):
            ride = active_rides[i % len(active_rides)]
            st = statuses[i % len(statuses)]
            EmergencyAlert.objects.create(
                ride=ride, rider=ride.rider, raised_by=ride.rider if kind == "sos" else None,
                kind=getattr(EmergencyAlert.Kind, kind.upper()),
                latitude=ride.pickup_lat, longitude=ride.pickup_lng, location=ride.pickup_location,
                message=ALERT_MESSAGES[kind], status=st,
                resolved_at=now if st == EmergencyAlert.Status.RESOLVED else None,
            )

        # ---- Incident reports ----
        completed = list(Ride.objects.filter(status=Ride.Status.COMPLETED)[:5])
        categories = ["Unsafe driving", "Harassment", "Overcharging", "Vehicle condition", "Other"]
        for i, ride in enumerate(completed):
            IncidentReport.objects.create(
                ride=ride, reporter=ride.rider, category=categories[i % len(categories)],
                description="Demo incident report describing what happened during the trip.",
                resolved=(i % 2 == 0),
            )

        self._summary()

    # ------------------------------------------------------------------ #
    def _user(self, email, name, phone, role, avatar="", status=None):
        user, _ = User.objects.get_or_create(
            email=email, defaults={"username": email, "name": name, "role": role}
        )
        user.username = email
        user.name = name
        user.phone = phone
        user.role = role
        user.avatar_url = avatar
        if status is not None:
            user.status = status
        user.set_password(PASSWORD)
        user.save()
        return user

    def _summary(self):
        self.stdout.write(self.style.SUCCESS("Done!"))
        self.stdout.write(
            f"Users: {User.objects.count()} | Rides: {Ride.objects.count()} | "
            f"Ratings: {Rating.objects.count()} | Alerts: {EmergencyAlert.objects.count()} | "
            f"Reports: {IncidentReport.objects.count()}"
        )
        self.stdout.write("\nLogins (password: password123):")
        self.stdout.write("  admin@safedrive.test    (admin)")
        self.stdout.write("  rider1..rider10@safedrive.test   (riders)")
        self.stdout.write("  driver1..driver7@safedrive.test  (approved drivers)")
        self.stdout.write("  driver8, driver9@safedrive.test  (pending drivers)")
        self.stdout.write("  driver10@safedrive.test          (suspended driver)")
