from digicampipe.image.kernels import *
from digicampipe.image.utils import *
from digicampipe.image.nova_client import Client
from astroquery.vizier import Vizier
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord, Angle
from astropy import units as u
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from matplotlib.patches import Circle, Rectangle, Arrow
import tempfile
from subprocess import run
import os
import shutil


class SkyImage(object):
    """SkyImage extract stars from an image and uses astrometry.net to try to get the galactic coordinates.
    To find stars, a spatial high pass filter is used.
    Computation of coordinates is done at construction only if a image_static is given.
    The static_image is removed from the filtered image (to keep only moving stars) prior of using astrometry."""
    def __init__(self, image, image_static=None, threshold=None,
                 scale_low_deg=None, scale_high_deg=None, calculate=False,
                 guess_ra_dec=None, guess_radius=None):
        if type(image) is str:
            image = fits.open(self.filename)[0].data
        if type(image) is not np.ndarray:
            raise AttributeError('image must be a filename or a numpy.ndarray')
        # high pass filter
        self.image_stars = signal.convolve2d(image, high_pass_filter_2525, mode='same', boundary='symm')
        self.image_stars[self.image_stars < 0] = 0
        # low_pass_filter
        self.image_stars = signal.convolve2d(self.image_stars, gauss(1, (5, 5)), mode='same', boundary='symm')
        self.image_stars[self.image_stars < 0] = 0
        self.scale_low_deg = scale_low_deg
        self.scale_high_deg = scale_high_deg
        self.guess_ra_dec = guess_ra_dec
        self.guess_radius = guess_radius
        if image_static is not None:
            self.subtract_static_image(image_static, threshold=threshold)
        self.sources_pixel = None
        self.reference_pixel = None
        self.reference_ra_dec = None
        self.cd_matrix = None
        self.stars_pixel = None
        self.wcs = None
        if calculate:
            self.calculate_galactic_coordinates(scale_low_deg=scale_low_deg, scale_high_deg=scale_high_deg)

    def subtract_static_image(self, image_static, threshold=None):
        """
        function which subtracts image_static to the filtered image to keep only the moving spikes.
        :param image_static: image subtracted to the filtered image
        :param threshold: pixels with a smaller value than threshold after subtraction are set to 0. Default at 100x the
            average pixel value after subtraction.
        :return:
        """
        if type(image_static) is not np.ndarray:
            raise AttributeError("image_static must be a numpy's ndarray.")
        self.image_stars = self.image_stars - image_static
        self.image_stars[self.image_stars < 0] = 0
        if threshold is None:
            threshold = np.std(self.image_stars)
        self.image_stars[self.image_stars < threshold] = 0

    def calculate_galactic_coordinates(self):
        if shutil.which('solve-field') is not None:
            self.calculate_galactic_coordinates_local()
        else:
            print('astrometry does not seem to be installed, using nova web service')
            self.calculate_galactic_coordinates_nova()

    def calculate_galactic_coordinates_local(self):
        """
        Use astrometry.net installed locally to determine galactic coordinates based on stars found.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            hdu = fits.PrimaryHDU(self.image_stars)
            outfile = os.path.join(tmpdir, 'stars.fits')
            hdu.writeto(outfile, overwrite=True)
            arguments = ['solve-field', outfile, '--no-plots', # '--no-background-subtraction', '--no-verify-uniformize',
                         # '--ra', str(83.2), '--dec', str(26.2), '--radius', str(10),
                         '--depth', '60']
            if self.guess_ra_dec is not None and self.guess_radius is not None:
                arguments.append('--ra')
                arguments.append(str(self.guess_ra_dec[0]))
                arguments.append('--dec')
                arguments.append(str(self.guess_ra_dec[1]))
                arguments.append('--radius')
                arguments.append(str(self.guess_radius))
            if self.scale_low_deg is not None or self.scale_high_deg is not None:
                arguments.append('--scale-units')
                arguments.append('degwidth')
            if self.scale_low_deg is not None:
                arguments.append('--scale-low')
                arguments.append(str(self.scale_low_deg))
            if self.scale_high_deg is not None:
                arguments.append('--scale-high')
                arguments.append(str(self.scale_high_deg))
            run(arguments)
            # sources position in image
            try:
                sources_data = fits.open(os.path.join(tmpdir, 'stars.axy'))[1].data
                self.sources_pixel = np.array((sources_data['X'], sources_data['Y']))
            except FileNotFoundError:
                self.sources_pixel = None
            # coordinate system
            try:
                header_wcs = fits.open(os.path.join(tmpdir, 'stars.wcs'))[0].header
                self.wcs = WCS(header_wcs)
                # reference point
                self.reference_pixel = (header_wcs['CRPIX1'], header_wcs['CRPIX2'])
                self.reference_ra_dec = (header_wcs['CRVAL1'], header_wcs['CRVAL2'])
                # transformation matrix
                self.cd_matrix = np.array(((header_wcs['CD1_1'], header_wcs['CD1_2']),
                                           (header_wcs['CD2_1'], header_wcs['CD2_2'])))
            except FileNotFoundError:
                self.wcs = None
                self.reference_pixel = None
                self.reference_ra_dec = None
                self.cd_matrix = None
            # stars position in image
            try:
                stars_data = fits.open(os.path.join(tmpdir, 'stars-indx.xyls'))[1].data
                self.stars_pixel = np.array((stars_data['X'], stars_data['Y']))
            except FileNotFoundError:
                self.stars_pixel = None

    def calculate_galactic_coordinates_nova(self):
        """
        Use the nova web service to determine galactic coordinates based on stars found.
        """
        import time
        from photutils import DAOStarFinder
        from astropy.table import Table

        apiurl='http://nova.astrometry.net/api/'
        c = Client(apiurl=apiurl)
        api_key = os.environ.get('NOVA_API_KEY', None)
        if api_key is None:
            raise EnvironmentError('NOVA_API_KEY environment variable must be set')
        c.login(api_key)
        jobs = c.myjobs()
        mean, median, std = sigma_clipped_stats(self.image_stars, sigma=3.0, iters=5)
        baseline_sub = self.image_stars - median
        baseline_sub[baseline_sub < 0] = 0
        daofind = DAOStarFinder(fwhm=3.0, threshold=std)
        sources = daofind(baseline_sub)
        self.sources_pixel = np.array([sources['xcentroid'], sources['ycentroid']])
        order = np.argsort(sources['mag'])
        n_peak = np.min([len(order), 100])
        self.sources_pixel = self.sources_pixel[:, order[0:n_peak]]

        with tempfile.TemporaryDirectory() as tmpdir:
            stars_filename = os.path.join(tmpdir, 'stars.txt')
            f = open(stars_filename, "w")
            for source in self.sources_pixel.transpose():
                f.write(str(round(source[0], 6)) + "\t" + str(round(source[1], 6)) + "\n")
            f.close()
            kwargs = dict(
                allow_commercial_use='n',
                allow_modifications='n',
                publicly_visible='y',
                )
            if self.guess_ra_dec is not None and self.guess_radius is not None:
                kwargs['center_ra'] = str(self.guess_ra_dec[0])
                kwargs['center_dec'] = str(self.guess_ra_dec[1])
                kwargs['radius'] = str(self.guess_radius)
            if self.scale_low_deg is not None or self.scale_high_deg is not None:
                kwargs['scale_units'] = 'degwidth'
                kwargs['scale_type'] = 'ul'
            if self.scale_low_deg is not None:
                kwargs['scale_lower'] = str(self.scale_low_deg)
            if self.scale_high_deg is not None:
                kwargs['scale_upper'] = str(self.scale_high_deg)
            upres = c.upload(stars_filename, **kwargs)
            stat = upres['status']
            if stat != 'success':
                print('Upload failed: status', stat)
                print(upres)
                return
            sub_id = upres['subid']
            if sub_id is None:
                print("error getting submission id!")
                return
            while True:
                stat = c.sub_status(sub_id, justdict=True)
                print('Got status:', stat)
                if stat is None:
                    continue
                jobs = stat.get('jobs', [])
                if len(jobs):
                    for j in jobs:
                        if j is not None:
                            break
                    if j is not None:
                        print('Selecting job id', j)
                        solved_id = j
                        break
                time.sleep(5)
            while True:
                stat = c.job_status(solved_id, justdict=True)
                print('Got job status:', stat)
                if stat.get('status', '') in ['success', 'failure']:
                    success = (stat['status'] == 'success')
                    break
                time.sleep(5)
            retrieve_urls = []
            if success:
                wcs_file = os.path.join(tmpdir, 'stars.wcs')
                corr_file = os.path.join(tmpdir, 'stars.corr')
                retrieve_urls.append((apiurl.replace('/api/', '/wcs_file/%i' % solved_id), wcs_file))
                retrieve_urls.append((apiurl.replace('/api/', '/corr_file/%i' % solved_id), corr_file))
            for url, fn in retrieve_urls:
                print('Retrieving file from', url, 'to', fn)
                f = None
                while f is None:
                    try:
                        f = urlopen(url)
                    except HTTPError as err:
                        print("ERROR", err, "getting url", url)
                        f = None
                        break
                if f is None:
                    continue
                txt = f.read()
                w = open(fn, 'wb')
                w.write(txt)
                w.close()
                print('Wrote to', fn)
            # coordinate system
            self.wcs = None
            self.reference_pixel = None
            self.reference_ra_dec = None
            self.cd_matrix = None
            if success:
                try:
                    header_wcs = fits.open(wcs_file)[0].header
                    self.wcs = WCS(header_wcs)
                    # reference point
                    self.reference_pixel = (header_wcs['CRPIX1'], header_wcs['CRPIX2'])
                    self.reference_ra_dec = (header_wcs['CRVAL1'], header_wcs['CRVAL2'])
                    # transformation matrix
                    self.cd_matrix = np.array(((header_wcs['CD1_1'], header_wcs['CD1_2']),
                                               (header_wcs['CD2_1'], header_wcs['CD2_2'])))
                except FileNotFoundError:
                    pass
            # stars position in image
            self.stars_pixel = None
            if success:
                try:
                    stars_data = fits.open(corr_file)[1].data
                    self.stars_pixel = np.array((stars_data['index_x'], stars_data['index_y']))
                except FileNotFoundError:
                    pass


class LidCCDImage(object):
    """
    LidCCDImage takes an image and  a list of areas of interest and create a SkyImage for each area.
    """
    def __init__(self, filename, crop_pixels1, crop_pixels2, image_static=None,
                 threshold=None, scale_low_images_deg=None, scale_high_images_deg=None,
                 guess_ra_dec=None, guess_radius=None):
        if type(filename) is not str:
            raise AttributeError('filename must be a string.')
        self.filename = filename
        if type(crop_pixels1) is not list:
            raise AttributeError('crop_pixels1 must be a list of pixels.')
        if type(crop_pixels2) is not list:
            raise AttributeError('crop_pixels2 must be a list of pixels.')
        if len(crop_pixels1) != len(crop_pixels2):
            raise AttributeError('crop_pixels1 and crop_pixels2 lists must have the same length.')
        image = fits.open(self.filename)[0].data
        self.image_shape = image.shape
        self.crop_pixels1 = []
        self.crop_pixels2 = []
        self.sky_images = []
        self.sky_images_shape = []
        print('divide', filename, 'in', len(crop_pixels1), 'sub-areas')
        for crop_pixel1, crop_pixel2 in zip(crop_pixels1, crop_pixels2):
            image_cropped, crop_pixel1, crop_pixel2 = crop_image(filename, crop_pixel1, crop_pixel2)
            ratios = [self.image_shape[0] / image_cropped.shape[0], self.image_shape[1] / image_cropped.shape[1]]
            scale_low_crop_deg = scale_low_images_deg / np.max(ratios)
            scale_high_crop_deg = scale_high_images_deg / np.min(ratios)
            self.crop_pixels1.append(crop_pixel1)
            self.crop_pixels2.append(crop_pixel2)
            self.sky_images_shape.append(image_cropped.shape)
            sky_image = SkyImage(image_cropped, image_static=image_static, threshold=threshold,
                                 scale_low_deg=scale_low_crop_deg,
                                 scale_high_deg=scale_high_crop_deg,
                                 guess_ra_dec=guess_ra_dec, guess_radius=guess_radius)
            self.sky_images.append(sky_image)
        self.center_px = None
        self.center_ra_dec = None
        self.CD = None
        self.wcs = None
        self.combine_coordinates()

    def subtract_static_images(self, static_images, threshold=None):
        for sky_image, static_image in zip(self.sky_images, static_images):
            sky_image.subtract_static_image(static_image, threshold=threshold)

    def calculate_galactic_coordinates(self):
        for sky_image in self.sky_images:
            sky_image.calculate_galactic_coordinates()
        self.combine_coordinates()

    def combine_coordinates(self):
        """
        Combining of coordinates from different regions of the image not implemented yet.
         Using of the 1st coordinates found instead.
        """
        wcs_list = []
        for sky_image, crop_pixel1 in zip(self.sky_images, self.crop_pixels1):
            if sky_image.reference_ra_dec is not None:
                wcs_list.append(sky_image.wcs)
        if len(wcs_list) > 0:
            self.wcs = wcs_list[0]

    def print_summary(self):
        print('matching result for', self.filename)
        for sky_image, crop_pixel1 in zip(self.sky_images, self.crop_pixels1):
            if sky_image.reference_ra_dec is not None:
                print('x pix =', sky_image.reference_pixel[0]+crop_pixel1[0])
                print('y pix =', sky_image.reference_pixel[1]+crop_pixel1[1])
                print('x ra =', sky_image.reference_ra_dec[0])
                print('y de =', sky_image.reference_ra_dec[1])
                print('CD =', sky_image.cd_matrix)

    def plot_image_solved(self, output_dir=None):
        """
        Superimpose found stars on the lid CCD image for each area of interest.
        If coordinates were found, it also shows the stars from the astrometry.net results.
        :param output_dir: directory where the resulting plot will be saved.
        """
        if output_dir is not None:
            plt.ioff()
        fig = plt.figure()
        ax = plt.gca()
        lid_image = fits.open(self.filename)[0].data
        if type(lid_image) is not np.ndarray:
            raise AttributeError([self.filename, ' must be a fit file'])
        plt.imshow(lid_image, cmap='gray')
        for sky_image, crop_pixel1, crop_pixel2 in zip(self.sky_images, self.crop_pixels1, self.crop_pixels2):
            if sky_image.sources_pixel is not None:
                for i in range(min(sky_image.sources_pixel.shape[1], 30)):
                    pixel_x = sky_image.sources_pixel[0, i] + crop_pixel1[0]
                    pixel_y = sky_image.sources_pixel[1, i] + crop_pixel1[1]
                    circle = Circle((pixel_x, pixel_y), radius=9, fill=False, color='r')
                    ax.add_artist(circle)
            if sky_image.stars_pixel is not None:
                for i in range(sky_image.stars_pixel.shape[1]):
                    pixel_x = sky_image.stars_pixel[0, i] + crop_pixel1[0]
                    pixel_y = sky_image.stars_pixel[1, i] + crop_pixel1[1]
                    circle = Circle((pixel_x, pixel_y), radius=11, fill=False, color='g')
                    ax.add_artist(circle)
            width = crop_pixel2[0] - crop_pixel1[0]
            height = crop_pixel2[1] - crop_pixel1[1]
            rect = Rectangle(crop_pixel1, width=width, height=height, fill=False, color='k', linestyle='dashdot')
            ax.add_artist(rect)
        plt.grid(None)
        plt.axis('off')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        if output_dir is None:
            plt.show()
        else:
            output_filename = self.filename.replace('.fits', '-solved.png')
            plt.savefig(output_filename, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            print(output_filename, 'saved.')

    def plot_image_treated(self, output_dir=None):
        """
        Superimpose stars and gamma sources on the lid CCD image.
        Internet acces is needed for the Vizier requests.
        :param output_dir: directory where the resulting plot will be saved.
        """
        if output_dir is not None:
            plt.ioff()
        fig = plt.figure()
        ax = plt.gca()
        lid_image = fits.open(self.filename)[0].data
        if type(lid_image) is not np.ndarray:
            raise AttributeError([self.filename, ' must be a fit file'])
        plt.imshow(lid_image, cmap='gray')
        image_treated = np.zeros(self.image_shape)
        vizier_blue = Vizier(columns=['all'], column_filters={"Bjmag": "<12"}, row_limit=-1, catalog=['I/271/out'])
        vizier_red = Vizier(columns=['all'], column_filters={"Rmag": "<12"}, row_limit=-1, catalog=['I/271/out'])
        vizier_green = Vizier(columns=['all'], column_filters={"Vmag": "<12"}, row_limit=-1, catalog=['I/271/out'])
        vizier_gamma = Vizier(columns=['all'], row_limit=-1, catalog=['J/ApJS/197/34'])
        for (sky_image, crop_pixel1, crop_pixel2) in zip(self.sky_images, self.crop_pixels1, self.crop_pixels2):
            image_treated[crop_pixel1[1]:crop_pixel2[1], crop_pixel1[0]:crop_pixel2[0]] = np.log(1+sky_image.image_stars)
            if sky_image.sources_pixel is not None:
                for i in range(min(sky_image.sources_pixel.shape[1], 30)):
                    pixel_x = sky_image.sources_pixel[0, i] + crop_pixel1[0]
                    pixel_y = sky_image.sources_pixel[1, i] + crop_pixel1[1]
                    circle = Circle((pixel_x, pixel_y), radius=20, fill=False, color='w')
                    ax.add_artist(circle)
            if sky_image.wcs is not None:
                self.center_px = np.array((self.image_shape[1], self.image_shape[0])).reshape(1, 2) / 2
                self.center_ra_dec = sky_image.wcs.wcs_pix2world(self.center_px - crop_pixel1, 1)[0]
                print('image center (ra, dec):', self.center_ra_dec)
                center_coordinate = SkyCoord(ra=self.center_ra_dec[0] * u.degree,
                                             dec=self.center_ra_dec[1] * u.degree, frame='icrs')
                result_blue = vizier_blue.query_region(center_coordinate, radius=Angle(5, "deg"),
                                                       catalog=['I/271/out'])[0]
                blue_stars_ra_dec = np.array((result_blue['RA_ICRS_'], result_blue['DE_ICRS_'])).transpose()  # .reshape((-1,2))
                blue_stars_mag = result_blue['Bjmag']
                blue_stars_px = sky_image.wcs.wcs_world2pix(blue_stars_ra_dec, 1)
                for star_px, star_mag in zip(blue_stars_px, blue_stars_mag):
                    if -5 < star_mag <= 12:
                        radius = 18 - star_mag
                    else:
                        radius = 5
                    circle = Circle((star_px[0] + crop_pixel1[0], star_px[1] + crop_pixel1[1]), radius=radius,
                                    fill=False, color='b')
                    ax.add_artist(circle)
                result_red = vizier_red.query_region(center_coordinate, radius=Angle(5, "deg"),
                                                     catalog=['I/271/out'])[0]
                red_stars_ra_dec = np.array((result_red['RA_ICRS_'], result_red['DE_ICRS_'])).transpose()  # .reshape((-1,2))
                red_stars_mag = result_red['Rmag']
                red_stars_px = sky_image.wcs.wcs_world2pix(red_stars_ra_dec, 1)
                for star_px, star_mag in zip(red_stars_px, red_stars_mag):
                    if -5 < star_mag <= 12:
                        radius = 18 - star_mag
                    else:
                        radius = 5
                    circle = Circle((star_px[0] + crop_pixel1[0], star_px[1] + crop_pixel1[1]), radius=radius,
                                    fill=False, color='r')
                    ax.add_artist(circle)
                result_green = vizier_green.query_region(center_coordinate, radius=Angle(5, "deg"),
                                                         catalog=['I/271/out'])[0]
                green_stars_ra_dec = np.array(
                    (result_green['RA_ICRS_'], result_green['DE_ICRS_'])).transpose()  # .reshape((-1,2))
                green_stars_mag = result_blue['Vmag']
                green_stars_px = sky_image.wcs.wcs_world2pix(green_stars_ra_dec, 1)
                for star_px, star_mag in zip(green_stars_px, green_stars_mag):
                    if -5 < star_mag <= 12:
                        radius = 18 - star_mag
                    else:
                        radius = 5
                    circle = Circle((star_px[0] + crop_pixel1[0], star_px[1] + crop_pixel1[1]), radius=radius,
                                    fill=False, color='g')
                    ax.add_artist(circle)
                result_gamma = vizier_gamma.query_region(center_coordinate, radius=Angle(5, "deg"),
                                                         catalog=['J/ApJS/197/34'])[0]
                gamma_stars_ra_dec = np.array((result_gamma['RAJ2000'], result_gamma['DEJ2000'])).transpose()  # .reshape((-1,2))
                gamma_stars_name = result_gamma['Name']
                gamma_stars_px = sky_image.wcs.wcs_world2pix(gamma_stars_ra_dec, 1)
                for star_px, gamma_star_name in zip(gamma_stars_px, gamma_stars_name):
                    circle = Circle((star_px[0] + crop_pixel1[0], star_px[1] + crop_pixel1[1]), radius=20,
                                    fill=False, color='Y')
                    ax.add_artist(circle)
                    ax.text(star_px[0] + crop_pixel1[0], star_px[1] + crop_pixel1[1], gamma_star_name, color='Y')
                crab_nebula_px = sky_image.wcs.wcs_world2pix(83.640187, 22.044295, 1)
                circle = Circle((crab_nebula_px[0] + crop_pixel1[0], crab_nebula_px[1] + crop_pixel1[1]), radius=20,
                                fill=False, color='Y')
                ax.add_artist(circle)
                ax.text(crab_nebula_px[0] + crop_pixel1[0], crab_nebula_px[1] + crop_pixel1[1], 'Crab Pulsar', color='Y')
            width = crop_pixel2[0] - crop_pixel1[0]
            height = crop_pixel2[1] - crop_pixel1[1]
            rect = Rectangle(crop_pixel1, width=width, height=height, fill=False, color='y', linestyle='dashdot')
            ax.add_artist(rect)
        # plt.imshow(image_treated, cmap='gray')
        plt.plot(0, 0, 'w+')
        plt.grid(None)
        plt.axis('off')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        if output_dir is None:
            plt.show()
        else:
            output_filename = self.filename.replace('.fits', '-treated.png')
            plt.savefig(output_filename, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            print(output_filename, 'saved.')


class LidCCDObservation:
    """
    LidCCDObservation regroups several LidCCDImages. Useful to find moving stars.
    """
    def __init__(self, filenames, crop_pixels1, crop_pixels2, threshold=None,
                 scale_low_images_deg=None, scale_high_images_deg=None,
                 guess_ra_dec=None, guess_radius=None):
        """
        Create a lid ccd observation from several pictures of the lid CCD camera.
        Pointing is determined for each of the regions defined.
        :param filenames: list of strings containing the path to lid CCD images (fits files).
        :param crop_pixels1: list of points defining the upper left corner of the region of interest in pixels
        :param crop_pixels2: list of points defining the lower right corner of the region of interest in pixels
        :param threshold: threshold: pixels with a smaller value than threshold after subtraction are set to 0. Default at 100x the
            average pixel value after subtraction.
        :param scale_low_images_deg: minimum field of view (in degrees) considered during fitting.
        :param scale_high_images_deg: maximum field of view (in degrees) considered during fitting.
        :param guess_ra_dec: aproximate pointing coordinates
        :param guess_radius: radius of pointing  coordinates around guess_ra_dec tried during determination
        """
        self.lidccd_images = []
        image_shape = None
        if type(filenames) is not list or len(filenames) == 0:
            raise AttributeError('filenames must be a non-empty list')
        for filename in filenames:
            lidccd_image = LidCCDImage(filename, crop_pixels1, crop_pixels2,
                                       scale_low_images_deg=scale_low_images_deg,
                                       scale_high_images_deg=scale_high_images_deg,
                                       guess_ra_dec = guess_ra_dec,
                                       guess_radius = guess_radius)
            if image_shape is None:
                image_shape = lidccd_image.image_shape
            elif image_shape != lidccd_image.image_shape:
                raise AttributeError('all images must have the same size')
            self.lidccd_images.append(lidccd_image)
        static_images = []
        for crop_area_index, crop_area_shape in enumerate(lidccd_image.sky_images_shape):
            # get static image for that area
            average_cropped = np.zeros(crop_area_shape)
            for lidccd_image in self.lidccd_images:
                average_cropped += lidccd_image.sky_images[crop_area_index].image_stars / len(self.lidccd_images)
            static_images.append(average_cropped * len(self.lidccd_images) / 4)
        # perform computation of coordinates
        for lidccd_image in self.lidccd_images:
            lidccd_image.subtract_static_images(static_images, threshold=threshold)
            lidccd_image.calculate_galactic_coordinates()

    def print_summary(self):
        for lidccd_image in self.lidccd_images:
            lidccd_image.print_summary()

    def plot_image_solved(self, outpout_dir=None):
        for lidccd_image in self.lidccd_images:
            lidccd_image.plot_image_solved(outpout_dir)

    def plot_image_treated(self, outpout_dir=None):
        for lidccd_image in self.lidccd_images:
            lidccd_image.plot_image_treated(outpout_dir)